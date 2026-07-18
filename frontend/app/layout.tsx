import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CallTree",
  description: "Decision-tree call guidance and call auditing",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <a href="/">CallTree</a>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
