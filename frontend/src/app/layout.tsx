import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Distributed AI Job Scheduler",
  description: "DAG-aware distributed job scheduler for English tutoring AI workloads",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
