import type { Metadata } from "next";
import "./globals.css";
import TopBar from "@/components/TopBar";

export const metadata: Metadata = {
  title: "CallTree",
  description: "Decision-tree call guidance and call auditing",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopBar />
        <main>{children}</main>
      </body>
    </html>
  );
}
