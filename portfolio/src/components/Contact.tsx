"use client";

import { motion } from "framer-motion";
import { Github, Linkedin, Mail } from "lucide-react";
import Link from "next/link";

export default function Contact() {
  return (
    <section id="contact" className="py-32 px-6 flex flex-col items-center justify-center min-h-[70vh] text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.5 }}
        className="max-w-2xl mx-auto space-y-8"
      >
        <p className="text-cyan-400 font-mono tracking-widest text-sm uppercase">
          04. What&apos;s Next?
        </p>
        <h2 className="text-5xl font-bold text-slate-200 tracking-tighter">
          Get In Touch
        </h2>
        <p className="text-slate-400 text-lg leading-relaxed max-w-xl mx-auto">
          Currently open for new opportunities. Whether you have a question about RAG systems, want to build safe LLM agents, or just want to say hi, my inbox is always open.
        </p>
        
        <div className="pt-8">
          <Link
            href="mailto:iamrohitpt@gmail.com"
            className="inline-block px-8 py-4 rounded-md border border-cyan-500 text-cyan-400 hover:bg-cyan-500/10 transition-all font-mono tracking-wide glow-effect"
          >
            Say Hello
          </Link>
        </div>

        <div className="flex justify-center gap-6 pt-16">
          <Link href="https://github.com/rohioffl" className="text-slate-500 hover:text-cyan-400 transition-colors">
            <Github className="w-6 h-6" />
          </Link>
          <Link href="https://linkedin.com/in/rohitpt" className="text-slate-500 hover:text-cyan-400 transition-colors">
            <Linkedin className="w-6 h-6" />
          </Link>
          <Link href="mailto:iamrohitpt@gmail.com" className="text-slate-500 hover:text-cyan-400 transition-colors">
            <Mail className="w-6 h-6" />
          </Link>
        </div>
      </motion.div>
    </section>
  );
}
