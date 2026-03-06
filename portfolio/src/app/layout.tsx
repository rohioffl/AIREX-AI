import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rohit P T | AI Engineer",
  description: "Portfolio of Rohit P T - AI Engineer specializing in LLM Applications and RAG.",
  keywords: ["Rohit P T", "AI Engineer", "LLM", "RAG", "Portfolio"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body
        className={`${inter.variable} font-sans bg-[#0B0F19] text-[#F1F5F9] antialiased overflow-x-hidden`}
      >
        {children}
      </body>
    </html>
  );
}
