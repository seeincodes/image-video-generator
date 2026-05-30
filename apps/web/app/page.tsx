import { Creator } from "@/components/Creator";

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <div className="eyebrow">MVP creator</div>
        <h1>Turn an image and a script into a short narrated video.</h1>
        <p className="lede">
          This skeleton wires the first product surface: prompt-to-image,
          image-to-video, voice generation, and final export as async jobs.
        </p>
      </section>

      <Creator />
    </main>
  );
}
