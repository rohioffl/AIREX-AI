"use client";

import { motion } from "framer-motion";
import SectionHeading from "./SectionHeading";
import { ExternalLink, Github, FolderGit2 } from "lucide-react";
import Link from "next/link";

const PROJECTS = [
  {
    title: "AIREX",
    description: "AI Incident Response Platform with RAG via pgvector, guarded action flows, SSE, and async workers.",
    tech: ["Python", "pgvector", "SSE", "Async Workers"],
    github: "https://github.com/rohioffl/AIREX",
    live: "https://airex.rohitpt.online"
  },
  {
    title: "Lens",
    description: "AWS to GCP Migration Automation Platform featuring Terraform and Kubernetes manifest generation.",
    tech: ["Terraform", "Kubernetes", "AWS", "GCP"],
    github: "#",
    live: "https://lens.ankercloud.com"
  },
  {
    title: "GCP Security Audit",
    description: "GCP Security Audit & Reporting Automation with Scout Suite and Gemini AI remediation suggestions.",
    tech: ["Python", "GCP", "Scout Suite", "Gemini AI"],
    github: "#",
    live: "#"
  }
];

export default function Projects() {
  return (
    <section id="projects" className="py-24 px-6 bg-slate-900/20">
      <div className="max-w-5xl mx-auto">
        <SectionHeading title="Featured Projects" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {PROJECTS.map((project, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="group relative flex flex-col justify-between h-full bg-[#0B0F19] rounded-xl border border-slate-800 p-8 hover:border-cyan-500/50 transition-all box-glow"
            >
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 to-purple-500 opacity-0 group-hover:opacity-100 transition-opacity rounded-t-xl" />
              
              <div>
                <div className="flex justify-between items-center mb-6">
                  <FolderGit2 className="w-10 h-10 text-cyan-400" />
                  <div className="flex gap-4">
                    <Link href={project.github} className="text-slate-400 hover:text-cyan-400 transition-colors">
                      <Github className="w-5 h-5" />
                    </Link>
                    <Link href={project.live} className="text-slate-400 hover:text-cyan-400 transition-colors">
                      <ExternalLink className="w-5 h-5" />
                    </Link>
                  </div>
                </div>
                
                <h3 className="text-xl font-bold text-slate-200 mb-3 group-hover:text-cyan-400 transition-colors">
                  {project.title}
                </h3>
                <p className="text-slate-400 text-sm leading-relaxed mb-6">
                  {project.description}
                </p>
              </div>

              <ul className="flex flex-wrap gap-3 mt-auto">
                {project.tech.map((item, i) => (
                  <li key={i} className="text-xs font-mono text-slate-500 px-2 py-1 bg-slate-800/50 rounded-md">
                    {item}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
