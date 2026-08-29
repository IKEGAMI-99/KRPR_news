(function exposePagination(root, factory) {
  const pagination = factory();
  if (typeof module === 'object' && module.exports) module.exports = pagination;
  if (root) root.KiraparaPagination = pagination;
}(typeof globalThis !== 'undefined' ? globalThis : this, () => {
  const PAGE_SIZE = 20;
  const REGIONS = Object.freeze(['ALL', 'JAPAN', 'CHINA', 'KOREA', 'GLOBAL']);

  function normalizeRegion(value) {
    const region = String(value || '').toUpperCase();
    return REGIONS.includes(region) ? region : 'ALL';
  }

  function normalizePage(value) {
    const page = Number.parseInt(String(value || ''), 10);
    return Number.isSafeInteger(page) && page > 0 ? page : 1;
  }

  function paginate(items, requestedPage, pageSize = PAGE_SIZE) {
    const source = Array.isArray(items) ? items : [];
    const size = Number.isSafeInteger(pageSize) && pageSize > 0 ? pageSize : PAGE_SIZE;
    const totalItems = source.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / size));
    const page = Math.min(normalizePage(requestedPage), totalPages);
    const startIndex = (page - 1) * size;
    const endIndex = Math.min(startIndex + size, totalItems);

    return Object.freeze({
      items: source.slice(startIndex, endIndex),
      page,
      pageSize: size,
      totalItems,
      totalPages,
      startNumber: totalItems ? startIndex + 1 : 0,
      endNumber: endIndex,
      hasPrevious: page > 1,
      hasNext: page < totalPages,
    });
  }

  return Object.freeze({ PAGE_SIZE, REGIONS, normalizeRegion, normalizePage, paginate });
}));
