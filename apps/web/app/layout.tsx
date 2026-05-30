import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Image Video Voice",
  description: "Create short AI videos from images, prompts, and voice narration.",
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
