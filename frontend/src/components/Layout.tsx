import { Outlet } from "react-router-dom";
import AppSidebar from "./AppSidebar";

export default function Layout() {
  return (
    <div className="flex min-h-screen w-full">
      <AppSidebar />
      <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
