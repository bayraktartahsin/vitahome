import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "VitaHome — the hospital saves your life, then hands you a piece of paper",
  description:
    "An agent fleet that executes medical instructions. Photograph the papers they gave you; VitaHome reconciles the medications, books the follow-ups, watches for the warning signs, and calls a human when one appears.",
  applicationName: "VitaHome",
  authors: [{ name: "Graviti Labs" }],
  openGraph: {
    title: "VitaHome",
    description:
      "The hospital saves your life, then hands you a piece of paper. We take it from there.",
    siteName: "VitaHome",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
