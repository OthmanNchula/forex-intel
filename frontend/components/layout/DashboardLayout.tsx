"use client";
import Sidebar from "./Sidebar";
import Header from "./Header";
import DisclaimerBanner from "@/components/shared/DisclaimerBanner";
import { useLivePrice } from "@/hooks/useLivePrice";
import { useStore } from "@/store/useStore";

function PriceFeed() {
  const { user } = useStore();
  const pairs = user?.preferred_pairs || ["EUR/USD", "GBP/USD", "XAU/USD"];
  useLivePrice(pairs);
  return null;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <PriceFeed />
      <Sidebar />
      <Header />
      <main className="ml-16 md:ml-56 pt-14 min-h-screen">
        <div className="p-4 space-y-4">
          <DisclaimerBanner />
          {children}
        </div>
      </main>
    </div>
  );
}