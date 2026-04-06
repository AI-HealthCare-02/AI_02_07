import Header from "@/components/layout/header";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main className="min-h-screen bg-[#090a0f]">{children}</main>
      <main className="min-h-screen bg-[#090a0f] pb-16 lg:pb-0">{children}</main>
    </>
  );
}
