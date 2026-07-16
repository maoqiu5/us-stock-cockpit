import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "美股驾驶舱",
  description: "MAG7 因子模型、回测评估、持仓纪律与自动执行监控平台"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
