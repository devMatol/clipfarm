import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "ClipFarm - Clips IA Verticaux en Local",
  description: "Transforme tes vidéos longues en clips verticaux prêts pour TikTok, YouTube Shorts et Instagram Reels",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased flex flex-col">
        <Providers>
          <Navbar />
          <main className="flex-1 container mx-auto max-w-6xl px-4 sm:px-6 py-8">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
