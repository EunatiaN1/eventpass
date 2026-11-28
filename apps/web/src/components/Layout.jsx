import { AnimatePresence, motion } from "framer-motion";
import { Navbar } from "./Navbar";

export function Layout({
  activeTab,
  onSelectTab,
  auth,
  onOpenAuth,
  onSignOut,
  toast,
  children,
}) {
  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white relative overflow-x-hidden">
      {/* Ambient luxury background gradients */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-32 h-[480px] w-[480px] rounded-full bg-[#FF6B00]/10 blur-[140px]" />
        <div className="absolute top-1/3 -left-40 h-[420px] w-[420px] rounded-full bg-[#00E676]/6 blur-[140px]" />
      </div>

      <Navbar
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        auth={auth}
        onOpenAuth={onOpenAuth}
        onSignOut={onSignOut}
      />

      <main className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 py-8 pb-24">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            className={`fixed bottom-6 right-6 z-50 max-w-md backdrop-blur-md bg-[#121212]/90 border shadow-2xl rounded-2xl px-5 py-3.5 text-sm font-medium ${
              toast.isError
                ? "border-red-500/40 text-red-200"
                : "border-[#00E676]/40 text-white"
            }`}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
