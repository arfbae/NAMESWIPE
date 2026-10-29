import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";
const MAX_IMAGE_CHARS = 8 * 1024 * 1024;

export type PaintColour = {
  name: string;
  hex: string;
  coveragePct: number;
  litres: number;
};

export type PaintPlan = {
  colours: PaintColour[];
  areaSqm: number;
  totalLitres: number;
  notes: string;
};

function friendlyError(err: unknown): string {
  const status =
    (err as { statusCode?: number })?.statusCode ??
    (err as { status?: number })?.status ??
    (err as { lastError?: { statusCode?: number } })?.lastError?.statusCode;
  if (status === 429) return "The AI service is busy. Please try again in a minute.";
  if (status === 402) return "AI credits are used up. Add credits to keep using this feature.";
  if (status === 403) return "AI access is currently blocked for this workspace.";
  if (status === 401) return "The AI service is not configured correctly.";
  return "The AI service could not complete this request. Please try again.";
}

async function requireUser() {
  const { resolveCaller } = await import("./gen-guard.server");
  const { userId } = await resolveCaller();
  if (!userId) throw new Error("Sign in to use AI writing and paint tools.");
  const key = process.env.LOVABLE_API_KEY;
  if (!key) throw new Error("The AI service is not configured.");
  return key;
}

const imageField = z.string().max(MAX_IMAGE_CHARS).nullable();

// ---------------------------------------------------------------------------
// Claude — proposal copywriter
// ---------------------------------------------------------------------------

export const writeProposalCopy = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      muralImageUrl: imageField,
      sceneName: z.string().max(200),
      clientName: z.string().max(200),
      projectTitle: z.string().max(200),
      location: z.string().max(300),
      wallDimensions: z.string().max(100),
      timeline: z.string().max(200),
      brief: z.string().max(2000),
    }),
  )
  .handler(async ({ data }) => {
    const key = await requireUser();
    const { createAnthropic } = await import("@ai-sdk/anthropic");
    const { streamText } = await import("ai");
    const { createLovableAiGatewayRunIdFetch } = await import("./ai/run-id");

    const runIdFetch = createLovableAiGatewayRunIdFetch();
    const anthropic = createAnthropic({
      baseURL: GATEWAY,
      apiKey: key,
      headers: { "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
      fetch: runIdFetch.fetch,
    });

    const facts = [
      ["Client", data.clientName],
      ["Project", data.projectTitle],
      ["Location", data.location],
      ["Wall", data.wallDimensions],
      ["Timeline", data.timeline],
      ["Concept name", data.sceneName],
      ["Artist's notes", data.brief],
    ]
      .filter(([, v]) => v.trim())
      .map(([k, v]) => `${k}: ${v}`)
      .join("\n");

    const content: Array<{ type: "text"; text: string } | { type: "image"; image: string }> = [];
    if (data.muralImageUrl) content.push({ type: "image", image: data.muralImageUrl });
    content.push({
      type: "text",
      text: `Write the "Concept & Scope" section for a client mural proposal.\n\n${facts || "No project details given."}\n\nThe attached image is the photorealistic mockup of the approved concept on the real wall.`,
    });

    try {
      const result = streamText({
        model: anthropic("anthropic/claude-sonnet-5"),
        maxOutputTokens: 2000,
        maxRetries: 0,
        system:
          "You are a senior copywriter for a professional mural studio. Write confident, warm, plain-English proposal copy for property owners and councils. Structure: one short paragraph describing the concept and how it transforms the site (refer to what is visible in the mockup), one paragraph on the community/brand value, then a short scope list (surface prep, priming, painting medium, protective coating, site safety/access, clean-up) as lines starting with '- '. Under 220 words. No headings, no markdown bold, no prices, never invent facts like dates or costs that were not given.",
        messages: [{ role: "user", content }],
      });
      const text = (await result.text).trim();
      const finish = await result.finishReason;
      if (!text) {
        throw new Error(
          finish === "content-filter"
            ? "The AI declined to write copy for this request."
            : "The AI returned no copy. Please try again.",
        );
      }
      return { text };
    } catch (err) {
      if (err instanceof Error && /declined|returned no copy/.test(err.message)) throw err;
      console.error("[ai:proposal-copy]", err);
      throw new Error(friendlyError(err));
    }
  });

// ---------------------------------------------------------------------------
// Gemini — palette & paint list
// ---------------------------------------------------------------------------

const LITRES_PER_SQM_PER_COAT = 1 / 8; // ~8 m² per litre exterior acrylic
const COATS = 2;
const WASTE = 1.15;

export const buildPaintPlan = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      imageUrls: z.array(z.string().max(MAX_IMAGE_CHARS)).min(1).max(4),
      areaSqm: z.number().positive().max(10000),
    }),
  )
  .handler(async ({ data }): Promise<PaintPlan> => {
    const key = await requireUser();
    const { streamText, Output, NoObjectGeneratedError } = await import("ai");
    const { createOpenAICompatible } = await import("@ai-sdk/openai-compatible");
    const { createLovableAiGatewayRunIdFetch } = await import("./ai/run-id");

    const runIdFetch = createLovableAiGatewayRunIdFetch();
    const gateway = createOpenAICompatible({
      name: "lovable",
      baseURL: GATEWAY,
      supportsStructuredOutputs: true,
      headers: { "Lovable-API-Key": key, "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
      fetch: runIdFetch.fetch,
    });

    const schema = z.object({
      colours: z.array(z.object({ name: z.string(), hex: z.string(), coveragePct: z.number() })),
      notes: z.string(),
    });

    let raw: z.infer<typeof schema>;
    try {
      const result = streamText({
        model: gateway("google/gemini-3.8-flash"),
        maxRetries: 0,
        output: Output.object({ schema }),
        messages: [
          {
            role: "user",
            content: [
              ...data.imageUrls.map((url) => ({ type: "image" as const, image: url })),
              {
                type: "text" as const,
                text: "These images are a mural artwork (and possibly its mockup on a wall). List the 6 to 12 distinct paint colours a muralist would need to paint the ARTWORK only (ignore the wall, sky and surroundings). For each give a short evocative paint name, a #RRGGBB hex value and the approximate percentage of the mural's painted area it covers; percentages should add up to about 100. In notes, give one or two sentences of practical painting advice (e.g. which colours need extra coats or a primer).",
              },
            ],
          },
        ],
      });
      raw = await result.output;
    } catch (err) {
      if (NoObjectGeneratedError.isInstance(err) && err.text) {
        try {
          raw = schema.parse(JSON.parse(err.text));
        } catch {
          throw new Error("Could not read the colour palette. Please try again.");
        }
      } else {
        console.error("[ai:paint-plan]", err);
        throw new Error(friendlyError(err));
      }
    }

    const cleaned = raw.colours
      .filter((c) => /^#?[0-9a-f]{6}$/i.test(c.hex.trim()))
      .slice(0, 12)
      .map((c) => ({
        name: c.name.trim().slice(0, 40) || "Colour",
        hex: c.hex.trim().startsWith("#") ? c.hex.trim() : `#${c.hex.trim()}`,
        coveragePct: Math.max(0, c.coveragePct),
      }));
    if (!cleaned.length) throw new Error("No colours could be identified in this artwork.");

    const sum = cleaned.reduce((s, c) => s + c.coveragePct, 0) || 1;
    const colours = cleaned
      .map((c) => {
        const pct = (c.coveragePct / sum) * 100;
        const litres =
          Math.ceil(data.areaSqm * (pct / 100) * LITRES_PER_SQM_PER_COAT * COATS * WASTE * 2) / 2;
        return { ...c, coveragePct: Math.round(pct), litres: Math.max(0.5, litres) };
      })
      .sort((a, b) => b.coveragePct - a.coveragePct);

    return {
      colours,
      areaSqm: data.areaSqm,
      totalLitres: colours.reduce((s, c) => s + c.litres, 0),
      notes: raw.notes.trim().slice(0, 400),
    };
  });

// ---------------------------------------------------------------------------
// Gemini — combined-mural composition planner
// ---------------------------------------------------------------------------

export type CompositionPlan = {
  heroIndex: number;
  order: number[];
  scales: number[];
  arrangement: string;
  bridges: string;
  palette: string[];
  rationale: string;
  directive: string;
};

export const planComposition = createServerFn({ method: "POST" })
  .inputValidator(
    z.object({
      artworkUrls: z.array(z.string().max(MAX_IMAGE_CHARS)).min(2).max(3),
      wallUrl: imageField,
      keepBackground: z.boolean(),
    }),
  )
  .handler(async ({ data }): Promise<CompositionPlan> => {
    const key = await requireUser();
    const { streamText, Output, NoObjectGeneratedError } = await import("ai");
    const { createOpenAICompatible } = await import("@ai-sdk/openai-compatible");
    const { createLovableAiGatewayRunIdFetch } = await import("./ai/run-id");

    const runIdFetch = createLovableAiGatewayRunIdFetch();
    const gateway = createOpenAICompatible({
      name: "lovable",
      baseURL: GATEWAY,
      supportsStructuredOutputs: true,
      headers: { "Lovable-API-Key": key, "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
      fetch: runIdFetch.fetch,
    });

    const n = data.artworkUrls.length;
    const schema = z.object({
      heroArtwork: z.number(),
      leftToRightOrder: z.array(z.number()),
      relativeScalePct: z.array(z.number()),
      arrangement: z.string(),
      bridges: z.string(),
      palette: z.array(z.string()),
      rationale: z.string(),
    });

    const content: Array<{ type: "text"; text: string } | { type: "image"; image: string }> = [];
    data.artworkUrls.forEach((url, i) => {
      content.push({ type: "text", text: `ARTWORK ${i + 1}:` });
      content.push({ type: "image", image: url });
    });
    if (data.wallUrl) {
      content.push({ type: "text", text: "WALL PHOTO (target surface):" });
      content.push({ type: "image", image: data.wallUrl });
    }
    content.push({
      type: "text",
      text: `You are a lead muralist planning ONE unified mural that combines these ${n} artworks${data.wallUrl ? " on the wall shown" : ""}. ${data.keepBackground ? "Each artwork's background is part of the piece." : "Only each artwork's main subject will be painted."}
Decide: heroArtwork (1-based number of the strongest focal piece); leftToRightOrder (1-based artwork numbers, every artwork exactly once); relativeScalePct (size of each artwork in that left-to-right order, hero = 100, others 30-80, follow Fibonacci-like 8:5:3 hierarchy); arrangement (one sentence: where each piece sits on the wall, using golden-section / rule-of-thirds positions${data.wallUrl ? " and avoiding windows, doors, pipes and occluders you can see" : ""}); bridges (one or two sentences: shared background wash, connecting motifs, overlaps or colour transitions that make the pieces read as one mural instead of separate stickers); palette (4-6 #RRGGBB unifying colours drawn from the artworks); rationale (two short plain-English sentences for the artist explaining why this works). Never invent new subjects.`,
    });

    let raw: z.infer<typeof schema>;
    try {
      const result = streamText({
        model: gateway("google/gemini-3.8-flash"),
        maxRetries: 0,
        output: Output.object({ schema }),
        messages: [{ role: "user", content }],
      });
      raw = await result.output;
    } catch (err) {
      if (NoObjectGeneratedError.isInstance(err) && err.text) {
        try {
          raw = schema.parse(JSON.parse(err.text));
        } catch {
          throw new Error("Could not read the composition plan. Please try again.");
        }
      } else {
        console.error("[ai:composition-plan]", err);
        throw new Error(friendlyError(err));
      }
    }

    // Normalise to 0-based, every artwork exactly once.
    const valid = (v: number) => Number.isInteger(v) && v >= 1 && v <= n;
    const seen = new Set<number>();
    const order = raw.leftToRightOrder
      .filter((v) => valid(v) && !seen.has(v) && seen.add(v))
      .map((v) => v - 1);
    for (let i = 0; i < n; i++) if (!order.includes(i)) order.push(i);
    const heroIndex = valid(raw.heroArtwork) ? raw.heroArtwork - 1 : order[0]!;
    const scales = order.map((idx, i) =>
      idx === heroIndex
        ? 100
        : Math.round(Math.min(90, Math.max(25, raw.relativeScalePct[i] ?? 60))),
    );
    const palette = raw.palette
      .map((h) => h.trim())
      .filter((h) => /^#?[0-9a-f]{6}$/i.test(h))
      .map((h) => (h.startsWith("#") ? h : `#${h}`))
      .slice(0, 6);
    const clip = (s: string, m: number) => s.trim().slice(0, m);
    const arrangement = clip(raw.arrangement, 400);
    const bridges = clip(raw.bridges, 400);

    const directive = [
      "ARTIST-APPROVED COMPOSITION PLAN (overrides the generic layout template where they differ):",
      `- Left-to-right order: ${order.map((i) => `Artwork ${i + 1}`).join(", ")}.`,
      `- Hero / focal piece: Artwork ${heroIndex + 1}. Relative sizes: ${order
        .map((idx, i) => `Artwork ${idx + 1} = ${scales[i]}%`)
        .join(", ")}.`,
      `- Placement: ${arrangement}`,
      `- Unify into one mural: ${bridges}`,
      palette.length ? `- Unifying palette accents: ${palette.join(", ")}.` : "",
      "- Every artwork's subject must still appear exactly as drawn; no new subjects.",
    ]
      .filter(Boolean)
      .join("\n");

    return {
      heroIndex,
      order,
      scales,
      arrangement,
      bridges,
      palette,
      rationale: clip(raw.rationale, 400),
      directive,
    };
  });
