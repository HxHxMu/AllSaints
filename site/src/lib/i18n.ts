// UI words and URLs for each language. English lives at /, Spanish at /es/.
// Brand copy (tagline, disclosure, credits) comes from brand.json; site_es holds the Spanish.
import type { Lang } from "./episodes";
import brand from "../../../brand/brand.json";

export const paths = {
  en: { home: "/", calendar: "/calendar/", saint: (slug: string) => `/saints/${slug}/`,
        patrons: "/patrons/", patron: (slug: string) => `/patrons/${slug}/`, places: "/places/", place: (slug: string) => `/places/${slug}/` },
  es: { home: "/es/", calendar: "/es/calendario/", saint: (slug: string) => `/es/santos/${slug}/`,
        patrons: "/es/patronos/", patron: (slug: string) => `/es/patronos/${slug}/`, places: "/es/lugares/", place: (slug: string) => `/es/lugares/${slug}/` },
};

export const t = {
  en: {
    calendar: "Calendar", watch: "▶ Watch the story", read: "Read the story", readFull: "Read the full story and prayer",
    yesterday: "‹ Yesterday", allSaints: "All saints ›", theCalendar: "The calendar", martyr: "Martyr",
    sources: "Sources", art: "Art", publicDomain: "public domain", candle: "🕯 Light a candle",
    candleSub: "Help keep the forgotten remembered.", feast: "Feast day", patron: "Patron of",
    menu: "Menu", menuClose: "Close menu", navLabel: "Main",
    feastDay: "Feast Day", places: "Places", byPatron: "By patronage", byPlace: "By place",
    patronsTitle: "Patron saints", patronsDesc: "Lesser-known Catholic saints by what they are patrons of.",
    placesTitle: "Saints by place", placesDesc: "Lesser-known Catholic saints by the places they lived, served and died.",
    patronOf: (n: string, count: number) => `Patron ${count === 1 ? "saint" : "saints"} of ${n}`,
    saintsOf: (n: string) => `Saints of ${n}`,
    topicDesc: (title: string, names: string) => `${title}: ${names}. Their stories and prayers, on their feast days.`,
    topicsNone: "None yet. The calendar grows every day.", count: (n: number) => `${n} ${n === 1 ? "saint" : "saints"}`,
    share: "Share this saint", shareSub: "Send the story to someone", shareFb: "Or share on Facebook",
    deeper: "Go deeper", booksFine: "Links go to Bookshop.org, which supports independent bookstores. All Saints earns a small commission on books bought there.",
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
    menu: "Menú", menuClose: "Cerrar menú", navLabel: "Principal",
    feastDay: "Fiesta", places: "Lugares", byPatron: "Por patronazgo", byPlace: "Por lugar",
    patronsTitle: "Santos patronos", patronsDesc: "Santos católicos poco conocidos, según su patronazgo.",
    placesTitle: "Santos por lugar", placesDesc: "Santos católicos poco conocidos, según los lugares donde vivieron, sirvieron y murieron.",
    patronOf: (n: string, count: number) => `${count === 1 ? "Santo patrono" : "Santos patronos"}: ${n}`,
    saintsOf: (n: string) => `Santos de ${n}`,
    topicDesc: (title: string, names: string) => `${title}: ${names}. Sus historias y oraciones, en su fiesta.`,
    topicsNone: "Todavía ninguno. El calendario crece cada día.", count: (n: number) => `${n} ${n === 1 ? "santo" : "santos"}`,
    share: "Comparte este santo", shareSub: "Envía la historia a alguien", shareFb: "O compártelo en Facebook",
    deeper: "Para profundizar", booksFine: "Libros en inglés. Los enlaces van a Bookshop.org, que apoya a las librerías independientes. All Saints recibe una pequeña comisión por los libros comprados allí.",
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
