import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Data Quality Observatory",
  description: "Real-time data quality monitoring and observability engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
            <footer className="border-t border-border px-6 py-3 text-center">
              <p className="text-xs text-text-secondary">
                Backend powered by Python + FastAPI · Check out the source on{" "}
                <a
                  href="https://github.com/asheth2310/data-quality-observability-engine"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline transition-colors duration-200"
                >
                  GitHub
                </a>
              </p>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
