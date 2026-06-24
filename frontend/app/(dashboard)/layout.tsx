"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser } from "@/lib/auth";
import { useStore } from "@/store/useStore";
import DashboardLayout from "@/components/layout/DashboardLayout";

export default function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { setUser, setToken } = useStore();

  useEffect(() => {
    const token = getToken();
    const user = getUser();
    if (!token || !user) {
      router.push("/login");
      return;
    }
    setToken(token);
    setUser(user);
  }, []);

  return <DashboardLayout>{children}</DashboardLayout>;
}