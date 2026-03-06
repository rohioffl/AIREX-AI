"use client";

import { motion } from "framer-motion";
import SectionHeading from "./SectionHeading";
import { Terminal } from "lucide-react";

export default function About() {
  return (
    <section id="about" className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <SectionHeading title="About Me" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5 }}
            className="space-y-6 text-slate-400 text-lg leading-relaxed"
          >
            <p>
              I am an AI Engineer with a strong focus on building Large Language Model applications, RAG pipelines, and safe orchestration architectures.
            </p>
            <p>
              My expertise lies in designing robust backend systems that bridge the gap between experimental AI concepts and production-ready applications. I heavily utilize <span className="text-cyan-400 font-medium">pgvector</span> for scalable vector search, and ensure agentic systems transition safely using strict state machines.
            </p>
            <p>
              When I&apos;m not architecting AI solutions, I&apos;m usually exploring new model capabilities, reading up on the latest in retrieval-augmented generation techniques, or optimizing database queries for high-throughput AI platforms.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="relative"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/10 to-purple-500/10 rounded-xl blur-xl" />
            <div className="relative rounded-xl border border-slate-800 bg-[#0B0F19]/80 backdrop-blur-md overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 bg-slate-900 border-b border-slate-800">
                <div className="w-3 h-3 rounded-full bg-rose-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                <div className="ml-4 flex items-center text-xs text-slate-500 font-mono gap-2">
                  <Terminal size={14} /> main.ts
                </div>
              </div>
              <div className="p-6 text-sm font-mono text-slate-300 overflow-x-auto">
                <pre>
                  <code className="text-cyan-400">const</code> <span className="text-purple-400">buildAI</span> <span className="text-cyan-400">=</span> <span className="text-cyan-400">async</span> () <span className="text-cyan-400">=&gt;</span> {"{"}
                  {"\n  "}<span className="text-cyan-400">const</span> rag <span className="text-cyan-400">=</span> <span className="text-cyan-400">new</span> <span className="text-amber-300">RagPipeline</span>({"{"}
                  {"\n    "}vectorStore: <span className="text-emerald-400">&quot;pgvector&quot;</span>,
                  {"\n    "}llm: <span className="text-emerald-400">&quot;GPT-4 / Claude-3.5&quot;</span>,
                  {"\n    "}embedding: <span className="text-emerald-400">&quot;OpenAI-v3&quot;</span>
                  {"\n  "}{"});"}
                  {"\n\n  "}<span className="text-cyan-400">const</span> app <span className="text-cyan-400">=</span> <span className="text-cyan-400">new</span> <span className="text-amber-300">Orchestrator</span>({"{"}
                  {"\n    "}safeTransitions: <span className="text-purple-400">true</span>,
                  {"\n    "}agenticWorkflows: <span className="text-purple-400">true</span>,
                  {"\n  "}{"});"}
                  {"\n\n  "}<span className="text-cyan-400">return</span> app.<span className="text-purple-400">deploy</span>(rag);
                  {"\n"}{"}"};
                </pre>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
