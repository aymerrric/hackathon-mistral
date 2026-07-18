"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { voiceWsUrl } from "@/lib/api";
import type { Tree } from "@/lib/types";

/**
 * Talk to the AI agent: full-duplex voice call in the browser.
 *
 * Mic audio is captured with an AudioWorklet, downsampled to 16 kHz PCM16
 * and streamed as binary WebSocket frames to /api/voice/ws, where Voxtral
 * realtime transcribes it and the tree-following agent answers. Agent speech
 * comes back as WAV (Voxtral TTS) and is played here; the mic is gated while
 * agent audio plays so the agent does not hear itself. If TTS fails the
 * agent text is spoken with the browser's speechSynthesis as a fallback.
 */

type Phase = "idle" | "connecting" | "live" | "ended" | "error";
type SubState = "listening" | "thinking" | "speaking";

interface LogEntry {
  role: "agent" | "caller";
  text: string;
}

const WORKLET_SRC = `
class PCMCapture extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(new Float32Array(ch));
    return true;
  }
}
registerProcessor("pcm-capture", PCMCapture);
`;

function downsampleTo16k(input: Float32Array, fromRate: number): Float32Array {
  if (fromRate === 16000) return input;
  const ratio = fromRate / 16000;
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const i1 = Math.min(i0 + 1, input.length - 1);
    out[i] = input[i0] + (input[i1] - input[i0]) * (pos - i0);
  }
  return out;
}

function toInt16(f32: Float32Array): Int16Array {
  const out = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const s = Math.max(-1, Math.min(1, f32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

export default function VoiceAgent({ tree }: { tree: Tree }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [sub, setSub] = useState<SubState>("listening");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [partial, setPartial] = useState("");
  const [nodeId, setNodeId] = useState<string | null>(null);
  const [visited, setVisited] = useState<string[]>([]);
  const [callRowId, setCallRowId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pendingRef = useRef<Float32Array[]>([]);
  const pendingLenRef = useRef(0);
  const gateRef = useRef(false); // true -> drop mic frames (agent speaking)
  const queueRef = useRef<string[]>([]);
  const playingRef = useRef(false);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const doneRef = useRef(false);
  const lastAgentTextRef = useRef("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log, partial]);

  useEffect(() => () => teardown(), []); // eslint-disable-line react-hooks/exhaustive-deps

  function teardown() {
    wsRef.current?.close();
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    audioElRef.current?.pause();
    audioElRef.current = null;
    queueRef.current = [];
    playingRef.current = false;
    window.speechSynthesis?.cancel();
  }

  const endCall = useCallback((reason?: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "end" }));
    }
    teardown();
    setPhase(reason ? "error" : "ended");
    if (reason) setError(reason);
  }, []);

  function speakFallback(text: string) {
    if (!window.speechSynthesis || !text) return;
    gateRef.current = true;
    setSub("speaking");
    const u = new SpeechSynthesisUtterance(text);
    u.onend = () => {
      gateRef.current = false;
      setSub("listening");
      if (doneRef.current) endCall();
    };
    window.speechSynthesis.speak(u);
  }

  function maybePlay() {
    if (playingRef.current || queueRef.current.length === 0) return;
    const b64 = queueRef.current.shift()!;
    playingRef.current = true;
    gateRef.current = true;
    setSub("speaking");
    const audio = new Audio(`data:audio/wav;base64,${b64}`);
    audioElRef.current = audio;
    const finish = () => {
      playingRef.current = false;
      if (queueRef.current.length > 0) {
        maybePlay();
      } else {
        gateRef.current = false;
        setSub("listening");
        if (doneRef.current) endCall();
      }
    };
    audio.onended = finish;
    audio.onerror = finish;
    audio.play().catch(finish);
  }

  function handleMessage(raw: string) {
    let msg: any;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }
    switch (msg.type) {
      case "ready":
        setPhase("live");
        setNodeId(msg.node_id);
        setVisited([msg.node_id]);
        setLog([{ role: "agent", text: msg.greeting }]);
        lastAgentTextRef.current = msg.greeting;
        break;
      case "audio":
        queueRef.current.push(msg.wav);
        maybePlay();
        break;
      case "partial":
        setPartial(msg.text);
        break;
      case "user":
        setPartial("");
        setSub("thinking");
        setLog((l) => [...l, { role: "caller", text: msg.text }]);
        break;
      case "agent":
        if (msg.call_id) setCallRowId(msg.call_id);
        if (!msg.text) break; // server-side close notification
        setLog((l) => [...l, { role: "agent", text: msg.text }]);
        lastAgentTextRef.current = msg.text;
        setNodeId(msg.node_id);
        if (msg.stepped) setVisited((v) => [...v, msg.node_id]);
        if (msg.done) doneRef.current = true;
        setSub("speaking"); // audio frame follows right after
        break;
      case "error":
        if (typeof msg.detail === "string" && msg.detail.startsWith("TTS failed")) {
          speakFallback(lastAgentTextRef.current);
        } else {
          setError(msg.detail);
        }
        break;
    }
  }

  async function start() {
    setError(null);
    setPhase("connecting");
    doneRef.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
      streamRef.current = stream;
      const ctx = new AudioContext({ sampleRate: 16000 });
      ctxRef.current = ctx;
      const blob = new Blob([WORKLET_SRC], { type: "application/javascript" });
      await ctx.audioWorklet.addModule(URL.createObjectURL(blob));
      const source = ctx.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(ctx, "pcm-capture");
      source.connect(node);

      const operator = localStorage.getItem("calltree:operator") ?? "";
      const ws = new WebSocket(voiceWsUrl(tree.id, operator));
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      node.port.onmessage = (e: MessageEvent<Float32Array>) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        // While agent audio plays, stream silence instead of stopping: a
        // continuous timeline keeps the transcriber flushing its tail and
        // stops the agent from hearing itself.
        if (gateRef.current) e.data.fill(0);
        pendingRef.current.push(e.data);
        pendingLenRef.current += e.data.length;
        // ~128 ms at the context rate before shipping a frame
        if (pendingLenRef.current >= ctx.sampleRate / 8) {
          const merged = new Float32Array(pendingLenRef.current);
          let off = 0;
          for (const c of pendingRef.current) {
            merged.set(c, off);
            off += c.length;
          }
          pendingRef.current = [];
          pendingLenRef.current = 0;
          const pcm = toInt16(downsampleTo16k(merged, ctx.sampleRate));
          ws.send(pcm.buffer);
        }
      };

      ws.onmessage = (e) => typeof e.data === "string" && handleMessage(e.data);
      ws.onerror = () => {
        if (phase !== "ended") endCall("Connection to the voice agent failed.");
      };
      ws.onclose = () => {
        setPhase((p) => (p === "live" || p === "connecting" ? "ended" : p));
        teardown();
      };
    } catch (e) {
      teardown();
      setPhase("error");
      setError(
        e instanceof Error && e.name === "NotAllowedError"
          ? "Microphone access was denied. Allow the microphone and retry."
          : e instanceof Error
            ? e.message
            : String(e)
      );
    }
  }

  const node = nodeId ? tree.structure.nodes[nodeId] : null;

  // --- Idle / ended / error screens ------------------------------------
  if (phase === "idle" || phase === "error" || phase === "ended") {
    return (
      <div className="card" style={{ maxWidth: 560 }}>
        {phase === "ended" ? (
          <>
            <span className="end-banner">Voice call finished</span>
            <p className="muted" style={{ margin: "12px 0 16px" }}>
              The session was saved to the Log
              {callRowId ? " and the transcript is ready to audit" : ""}.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button className="btn btn-primary" onClick={() => { setLog([]); setVisited([]); setCallRowId(null); setPhase("idle"); }}>
                New voice call
              </button>
              <a className="btn btn-ghost" href={`/trees/${tree.id}/log`}>
                Open log
              </a>
              {callRowId && (
                <a className="btn btn-ghost" href={`/trees/${tree.id}/audit`}>
                  Audit it
                </a>
              )}
            </div>
          </>
        ) : (
          <>
            <p style={{ marginTop: 0 }}>
              Start a live voice call with the AI agent. It follows{" "}
              <strong>{tree.title}</strong> step by step: it asks the tree&apos;s
              questions, listens to you, and advances the procedure — you play
              the caller.
            </p>
            <button className="btn btn-primary btn-lg" onClick={start} autoFocus>
              Start voice call
            </button>
            {error && (
              <p className="error-text" style={{ marginBottom: 0 }}>{error}</p>
            )}
          </>
        )}
      </div>
    );
  }

  // --- Connecting / live ------------------------------------------------
  return (
    <div className="voice-layout">
      <div className="voice-main">
        <div className={`voice-orb ${phase === "connecting" ? "thinking" : sub}`}>
          <div className="voice-orb-core" />
        </div>
        <div className="voice-status">
          {phase === "connecting"
            ? "Connecting"
            : sub === "listening"
              ? "Listening — just talk"
              : sub === "thinking"
                ? "Thinking"
                : "Agent speaking"}
        </div>
        {partial && <div className="voice-partial">“{partial}”</div>}
        <button
          className="btn btn-danger-ghost"
          style={{ marginTop: 18 }}
          onClick={() => endCall()}
        >
          End call
        </button>
      </div>

      <div className="voice-side">
        {node && (
          <div className="voice-node">
            <div className="node-kicker">
              <span className={`tv-badge ${node.type}`} />
              Current step · {node.label}
            </div>
            <div className="crumbs" style={{ marginTop: 8, marginBottom: 0 }}>
              {visited.map((id, i) => (
                <span key={i} style={{ display: "contents" }}>
                  {i > 0 && <span className="crumb-arrow">›</span>}
                  <span
                    className="crumb"
                    style={i === visited.length - 1 ? { color: "var(--accent)" } : undefined}
                  >
                    {tree.structure.nodes[id]?.label ?? id}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="voice-log" ref={logRef}>
          {log.map((m, i) => (
            <div key={i} className={`voice-msg ${m.role}`}>
              <span className="voice-msg-who">
                {m.role === "agent" ? "Agent" : "You"}
              </span>
              {m.text}
            </div>
          ))}
          {partial && (
            <div className="voice-msg caller pending">
              <span className="voice-msg-who">You</span>
              {partial}…
            </div>
          )}
        </div>
        {error && <p className="error-text">{error}</p>}
      </div>
    </div>
  );
}
