import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MX Repair Desktop',
  description: 'Camera-centered repair assistant',
  icons: {
    icon: '/icon.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

