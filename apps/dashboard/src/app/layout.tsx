import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IPMI-OS 2.0 Dashboard",
  description: "Real-time Probabilistic Market Intelligence for Gold and Crypto",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <header className="main-header">
          <div className="header-logo">
            <span className="logo-spark">✨</span>
            <span className="logo-text">IPMI-OS <span className="logo-ver">2.0</span></span>
          </div>
          <div className="header-status">
            <span className="status-indicator live"></span>
            <span className="status-label">LIVE ENGINE ACTIVE</span>
          </div>
        </header>
        <main className="main-content">
          {children}
        </main>
        <footer className="main-footer">
          <p>© 2026 IPMI-OS. Probabilistic Machine Fusion Market Intelligence.</p>
        </footer>
      </body>
    </html>
  );
}
