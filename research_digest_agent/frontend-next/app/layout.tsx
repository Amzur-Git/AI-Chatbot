import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Digest Agent",
  description: "Live AI research digest with arXiv + LangGraph",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
