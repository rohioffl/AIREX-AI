"use client";

import { motion } from "framer-motion";
import SectionHeading from "./SectionHeading";
import { Briefcase } from "lucide-react";

const EXPERIENCES = [
  {
    company: "Ankercloud Technologies Pvt. Ltd.",
    role: "Site Reliability Engineer",
    duration: "Jul 2024 - Present",
    description: [
      "Reduced deployment time by ~80% and MTTR by ~40%.",
      "Saved $10k+ annually through infrastructure optimization and automation.",
      "Engineered secure, deterministic transitions in complex workflows.",
      "Collaborated on building robust systems to trace performance and usage."
    ]
  },
  {
    company: "Progellies Technologies",
    role: "DevOps Intern",
    duration: "Nov 2023 - Jan 2024",
    description: [
      "Assisted in managing and deploying cloud infrastructure components.",
      "Optimized and streamlined data ingestion and CI/CD pipelines.",
      "Implemented security best practices for handling sensitive data.",
      "Built multiple Proof of Concepts for automation use cases."
    ]
  }
];

export default function Experience() {
  return (
    <section id="experience" className="py-24 px-6 relative">
      <div className="max-w-4xl mx-auto">
        <SectionHeading title="Experience" />
        <div className="relative border-l border-slate-800 ml-3 md:ml-4 pl-8 md:pl-10 space-y-16">
          {EXPERIENCES.map((exp, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="relative group"
            >
              {/* Timeline Marker */}
              <div className="absolute -left-[45px] md:-left-[53px] top-1 p-1 bg-[#0B0F19] border-2 border-slate-800 group-hover:border-cyan-500 rounded-full transition-colors duration-300">
                <Briefcase className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors duration-300" />
              </div>

              <div className="flex flex-col md:flex-row md:items-baseline md:justify-between mb-4">
                <h3 className="text-2xl font-bold text-slate-200">
                  {exp.role} <span className="text-cyan-500">@ {exp.company}</span>
                </h3>
                <span className="text-sm font-mono text-slate-500 mt-1 md:mt-0">
                  {exp.duration}
                </span>
              </div>
              
              <ul className="space-y-3">
                {exp.description.map((item, i) => (
                  <li key={i} className="flex gap-3 text-slate-400">
                    <span className="text-cyan-500 mt-1.5 text-xs">▹</span>
                    <span className="leading-relaxed">{item}</span>
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
