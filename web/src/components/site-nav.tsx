"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GITHUB_REPO } from "@/lib/site";

const LINKS = [
  { href: "/", label: "Notes" },
  { href: "/explore", label: "Sample" },
  { href: "/workbook", label: "Workbook" },
  { href: "/scripture", label: "Scripture" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Pages">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link key={link.href} href={link.href} aria-current={active ? "page" : undefined}>
            {link.label}
          </Link>
        );
      })}
      <a href={GITHUB_REPO}>GitHub</a>
    </nav>
  );
}
