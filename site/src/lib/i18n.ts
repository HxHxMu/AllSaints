// UI words and URLs for each language. English lives at /, Spanish at /es/.
// Brand copy (tagline, disclosure, credits) comes from brand.json; site_es holds the Spanish.
import type { Lang } from "./episodes";
import brand from "../../../brand/brand.json";

export const paths = {
  en: { home: "/", calendar: "/calendar/", saint: (slug: string) => `/saints/${slug}/` },
  es: { home: "/es/", calendar: "/es/calendario/", saint: (slug: string) => `/es/santos/${slug}/` },
};

export const t = {
  en: {
    calendar: "Calendar", watch: "▶ Watch the story", read: "Read the story", readFull: "Read the full story and prayer",
    yesterday: "‹ Yesterday", allSaints: "All saints ›", theCalendar: "The calendar", martyr: "Martyr",
    sources: "Sources", art: "Art", publicDomain: "public domain", candle: "🕯 Light a candle",
    candleSub: "Help keep the forgotten remembered.", feast: "Feast day", patron: "Patron of",
    litany: "The Litany", litanyDesc: "Every saint All Saints has remembered, day by day.",
    find: "Find a saint or a place…", findLabel: "Find a saint", none: "No saint by that name yet. The calendar grows every day.",
    homeDesc: "One forgotten saint a day, on their feast day.", soon: "The first saint arrives soon.",
    otherDays: "Other days", play: (n: string) => `Play the one-minute story of ${n}`, icon: (n: string) => `Icon of ${n}`,
    about: "About", music: "Music", privacy: "Privacy", terms: "Terms", skip: "Skip to content", homeLabel: "All Saints, home",
    tagline: (brand as any).tagline as string,
    bandLine: "A week of saints, in one quiet email.", bandEmail: "Your email", bandButton: "Subscribe",
    bandFine: "Sundays. Confirm by email; unsubscribe anytime.", bandError: "That didn't go through. Check the address and try again.",
  },
  es: {
    calendar: "Calendario", watch: "▶ Ver la historia", read: "Leer la historia", readFull: "Leer la historia completa y la oración",
    yesterday: "‹ Ayer", allSaints: "Todos los santos ›", theCalendar: "El calendario", martyr: "Mártir",
    sources: "Fuentes", art: "Arte", publicDomain: "dominio público", candle: "🕯 Enciende una vela",
    candleSub: "Ayúdanos a que los olvidados sean recordados.", feast: "Fiesta", patron: "Patrono de",
    litany: "La Letanía", litanyDesc: "Cada santo que All Saints ha recordado, día a día.",
    find: "Busca un santo o un lugar…", findLabel: "Buscar un santo", none: "Aún no hay un santo con ese nombre. El calendario crece cada día.",
    homeDesc: "Un santo olvidado cada día, en su fiesta.", soon: "El primer santo llega pronto.",
    otherDays: "Otros días", play: (n: string) => `Ver la historia de un minuto de ${n}`, icon: (n: string) => `Icono de ${n}`,
    about: "Acerca de", music: "Música", privacy: "Privacidad", terms: "Términos", skip: "Ir al contenido", homeLabel: "All Saints, inicio",
    tagline: (brand as any).site_es.tagline as string,
    bandLine: "Una semana de santos, en un correo tranquilo.", bandEmail: "Tu correo", bandButton: "Suscribirme",
    bandFine: "Los domingos. Confirma por correo; puedes darte de baja cuando quieras.", bandError: "No se pudo completar. Revisa el correo e inténtalo de nuevo.",
  },
} satisfies Record<Lang, Record<string, unknown>>;
