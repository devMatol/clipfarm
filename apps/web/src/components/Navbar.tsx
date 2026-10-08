import Link from "next/link";
import { Sparkles, PlusCircle, Video } from "lucide-react";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/90 backdrop-blur-md">
      <div className="container mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-bold text-xl tracking-tight text-white hover:opacity-90 transition">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-500 shadow-md shadow-purple-900/30">
            <Video className="h-5 w-5 text-white" />
          </div>
          <span>
            Clip<span className="text-purple-400">Farm</span>
          </span>
          <span className="rounded-full bg-purple-500/10 px-2 py-0.5 text-xs font-semibold text-purple-400 border border-purple-500/20">
            Local AI
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          <Link href="/" className="text-muted-foreground hover:text-white transition">
            Projets
          </Link>
          <Link href="/calendar" className="text-muted-foreground hover:text-white transition flex items-center gap-1.5">
            <span className="text-purple-400">📅</span> Calendrier
          </Link>
          <Link href="/publications" className="text-muted-foreground hover:text-white transition">
            Publications
          </Link>
          <Link href="/accounts" className="text-muted-foreground hover:text-white transition">
            Comptes
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/accounts"
            className="md:hidden text-xs text-muted-foreground hover:text-white transition"
          >
            Comptes
          </Link>
          <Link
            href="/projects/new"
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-purple-500 active:scale-95 transition"
          >
            <PlusCircle className="h-4 w-4" />
            <span>Nouveau projet</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
