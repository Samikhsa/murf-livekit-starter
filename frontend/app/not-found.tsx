export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground px-6 py-12">
      <div className="max-w-xl text-center">
        <h1 className="text-4xl font-bold mb-4">Page not found</h1>
        <p className="text-base leading-7 text-muted-foreground">
          The page you are looking for does not exist. Please check the URL and try again.
        </p>
      </div>
    </div>
  );
}
