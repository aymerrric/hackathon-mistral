"use client";

/**
 * Audio file picker + upload button with progress states. TO IMPLEMENT.
 *
 * Spec:
 *  - Accepts .mp3/.wav/.m4a (input accept attr + reject others with an
 *    inline error). Show the chosen filename and size.
 *  - onUpload(file) is async (parent calls api.uploadCall); render the
 *    provided `busyLabel` while awaiting ("Transcribing with Voxtral…").
 *  - Surface thrown errors inline in red below the button.
 */
export interface AudioUploaderProps {
  busyLabel: string;
  onUpload: (file: File) => Promise<void>;
}

export default function AudioUploader(props: AudioUploaderProps) {
  return <p>TODO: implement AudioUploader</p>;
}
