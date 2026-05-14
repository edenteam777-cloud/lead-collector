export default async () => {
  try {
    await fetch("https://lead-collector-nl89.onrender.com/api/historico");
  } catch {}
};

export const config = {
  schedule: "*/14 * * * *",
};
