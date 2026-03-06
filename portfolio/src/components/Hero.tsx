"use client";

import { motion } from "framer-motion";
import { FileText, Github, Linkedin, Mail } from "lucide-react";
import Link from "next/link";

export default function Hero() {
  return (
    <section className="min-h-screen flex items-center justify-center relative pt-20 pb-16 px-6">
      <div className="absolute inset-0 z-0 opacity-20 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-[40rem] h-[40rem] bg-cyan-600 rounded-full mix-blend-screen filter blur-[128px] animate-blob" />
        <div className="absolute top-1/3 right-1/4 w-[35rem] h-[35rem] bg-purple-600 rounded-full mix-blend-screen filter blur-[128px] animate-blob animation-delay-2000" />
      </div>

      <div className="z-10 max-w-5xl mx-auto w-full">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="space-y-6"
        >
          <motion.p
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="text-cyan-400 font-mono tracking-wide"
          >
            Hi, my name is
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="text-5xl sm:text-7xl font-bold tracking-tighter text-slate-100"
          >
            Rohit P T.
          </motion.h1>
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="text-4xl sm:text-6xl font-bold tracking-tighter text-slate-400"
          >
            I build reliable <span className="text-cyan-400">AI systems</span>.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="text-lg text-slate-400 max-w-2xl leading-relaxed pt-4"
          >
            I&apos;m an AI Engineer (AI Systems / Cloud) specializing in LLM Applications, RAG (pgvector), and scalable, safe orchestration architectures. Focused on building robust, reliable, and traceable AI apps on AWS/GCP.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.5 }}
            className="flex flex-wrap gap-4 pt-8"
          >
            <Link
              href="https://drive.google.com/file/d/1wX3FSKEAEh_Qkj6rwJhRb4YrKN8_IDy0/view?usp=drivesdk"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 hover:border-cyan-500/40 transition-all font-medium"
            >
              <FileText className="w-5 h-5" />
              View Resume
            </Link>
            <Link
              href="https://github.com/rohioffl"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-slate-800/50 text-slate-200 border border-slate-700/50 hover:bg-slate-700 hover:text-white transition-all font-medium"
            >
              <Github className="w-5 h-5" />
              GitHub
            </Link>
            <Link
              href="https://linkedin.com/in/rohitpt"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center p-3 rounded-lg bg-slate-800/50 text-slate-400 border border-slate-700/50 hover:text-white hover:bg-slate-700 transition-all"
              aria-label="LinkedIn"
            >
              <Linkedin className="w-5 h-5" />
            </Link>
            <Link
              href="mailto:iamrohitpt@gmail.com"
              className="inline-flex items-center justify-center p-3 rounded-lg bg-slate-800/50 text-slate-400 border border-slate-700/50 hover:text-white hover:bg-slate-700 transition-all"
              aria-label="Email"
            >
              <Mail className="w-5 h-5" />
            </Link>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
