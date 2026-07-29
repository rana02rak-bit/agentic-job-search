import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RahulGPT — Job Intelligence",
  description: "AI-assisted job discovery, ranking, and outreach preparation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
