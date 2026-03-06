"use client";

import { motion } from "framer-motion";
import SectionHeading from "./SectionHeading";

const SKILL_CATEGORIES = [
  {
    title: "AI Systems",
    skills: ["RAG Architecture", "LLM Fine-Tuning", "Prompt Engineering", "pgvector", "LangChain", "LlamaIndex"]
  },
  {
    title: "Backend",
    skills: ["Python", "FastAPI", "TypeScript", "Node.js", "PostgreSQL", "Redis"]
  },
  {
    title: "Cloud & Platform",
    skills: ["AWS", "Google Cloud", "Docker", "Kubernetes", "CI/CD", "Terraform"]
  },
  {
    title: "Observability",
    skills: ["Prometheus", "Grafana", "Datadog", "Tracing", "Logging", "Langfuse"]
  }
];

export default function Skills() {
  return (
    <section id="skills" className="py-24 px-6 relative">
      <div className="max-w-4xl mx-auto">
        <SectionHeading title="Skills Overview" />
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-16">
          {SKILL_CATEGORIES.map((category, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: idx * 0.1 }}
              className="group"
            >
              <h3 className="text-xl font-bold text-slate-200 mb-6 flex items-center">
                <span className="w-8 h-[1px] bg-cyan-500/50 mr-4" />
                {category.title}
              </h3>
              <ul className="grid grid-cols-2 gap-4">
                {category.skills.map((skill, i) => (
                  <li key={i} className="flex items-center text-slate-400 group-hover:text-slate-300 transition-colors">
                    <span className="text-cyan-500 mr-2 font-mono text-sm">▸</span>
                    {skill}
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
