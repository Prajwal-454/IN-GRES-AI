import IngresMap from "@/components/IngresMap";

export default function Weather() {
  return (
    // Full-bleed: cancels AppShell's p-6 and fills the viewport below the header.
    <div className="-m-6 h-[calc(100vh-4rem)] w-[calc(100%+3rem)] overflow-hidden">
      <IngresMap />
    </div>
  );
}
