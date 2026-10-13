import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { TraceDeskQueue } from "./queue";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
  title: "TraceDesk",
  description: "Raise a carrier trace from a shipped order and save the claim packet.",
};

export default function TraceDeskPage() {
  return (
    <div className={`${plexSans.variable} ${plexMono.variable} ${plexSans.className} tracedesk`}>
      <TraceDeskQueue />
    </div>
  );
}
