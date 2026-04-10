import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const reikai = defineCollection({
  loader: glob({ base: './src/content/reikai', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    location: z.string().optional(),
    meetingPoint: z.string().optional(),
    participants: z.number().optional(),
    organizer: z.string().optional(),
    reporter: z.string(),
    photographer: z.string().optional(),
  }),
});

const kaihou = defineCollection({
  loader: glob({ base: './src/content/kaihou', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    issueNumber: z.number(),
    publishDate: z.coerce.date(),
    hasFullText: z.boolean().default(false),
  }),
});

const news = defineCollection({
  loader: glob({ base: './src/content/news', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    tag: z.enum(['NEW', 'INFO', 'EVENT']).default('INFO'),
  }),
});

const kaiinhassin = defineCollection({
  loader: glob({ base: './src/content/kaiinhassin', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    author: z.string().optional(),
  }),
});

export const collections = { reikai, kaihou, news, kaiinhassin };
