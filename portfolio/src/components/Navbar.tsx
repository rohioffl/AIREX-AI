"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5 }}
      className={`fixed top-0 w-full z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[#0B0F19]/80 backdrop-blur-md border-b border-slate-800 shadow-lg"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold tracking-tighter text-slate-200">
          R<span className="text-cyan-500">.</span>
        </Link>
        
        <nav className="hidden md:flex gap-8 text-sm font-mono text-slate-400">
          <Link href="#about" className="hover:text-cyan-400 transition-colors">
            01. About
          </Link>
          <Link href="#experience" className="hover:text-cyan-400 transition-colors">
            02. Experience
          </Link>
          <Link href="#projects" className="hover:text-cyan-400 transition-colors">
            03. Projects
          </Link>
          <Link href="#skills" className="hover:text-cyan-400 transition-colors">
            04. Skills
          </Link>
          <Link href="#contact" className="hover:text-cyan-400 transition-colors">
            05. Contact
          </Link>
        </nav>
      </div>
    </motion.header>
  );
}
