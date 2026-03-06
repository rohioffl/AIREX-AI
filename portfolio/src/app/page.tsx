import Hero from "@/components/Hero";
import About from "@/components/About";
import Experience from "@/components/Experience";
import Projects from "@/components/Projects";
import Skills from "@/components/Skills";
import Contact from "@/components/Contact";
import Navbar from "@/components/Navbar";

export default function Home() {
  return (
    <>
      <Navbar />
      <main className="min-h-screen selection:bg-cyan-500/30 selection:text-cyan-200">
        <Hero />
        <About />
        <Experience />
        <Projects />
        <Skills />
        <Contact />
        
        <footer className="py-8 text-center text-slate-500 font-mono text-sm border-t border-slate-800">
          <p>Built with Next.js & Tailwind CSS. Designed by Rohit P T.</p>
        </footer>
      </main>
    </>
  );
}
