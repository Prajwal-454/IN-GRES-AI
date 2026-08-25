export function useDocumentTitle(title: string) {
  const prev = document.title;
  document.title = title;
  return () => {
    document.title = prev;
  };
}