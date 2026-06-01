export function BlobBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
      <div className="blob blob-1 absolute top-[-10%] left-[-5%] w-[600px] h-[600px] rounded-full opacity-40 animate-blob-drift-1" />
      <div className="blob blob-2 absolute top-[60%] left-[70%] w-[500px] h-[500px] rounded-full opacity-30 animate-blob-drift-2" />
      <div className="blob blob-3 absolute top-[20%] left-[50%] w-[450px] h-[450px] rounded-full opacity-25 animate-blob-drift-3" />
      <div className="blob blob-4 absolute top-[-5%] left-[80%] w-[550px] h-[550px] rounded-full opacity-20 animate-blob-drift-4" />
      <div className="blob blob-5 absolute top-[40%] left-[10%] w-[400px] h-[400px] rounded-full opacity-25 animate-blob-drift-5" />
    </div>
  );
}
