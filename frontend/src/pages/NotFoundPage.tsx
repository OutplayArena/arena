import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 px-6">
      <h1 className="text-4xl font-black text-ink">404</h1>
      <p className="text-sm text-muted">Page not found</p>
      <Link
        to="/"
        className="px-5 py-2 rounded-input bg-accent text-white text-sm font-extrabold no-underline"
      >
        Go home
      </Link>
    </div>
  );
}
