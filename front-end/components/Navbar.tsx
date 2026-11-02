
import Logo from "./Logo";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 w-full bg-slate-800 border-b border-slate-700">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <Logo />
      </div>
    </header>
  );
}
