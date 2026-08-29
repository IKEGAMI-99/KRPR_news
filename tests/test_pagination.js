const assert = require('node:assert/strict');
const {
  PAGE_SIZE,
  normalizePage,
  normalizeRegion,
  paginate,
} = require('../docs/pagination.js');

assert.equal(PAGE_SIZE, 20);
assert.equal(normalizePage(undefined), 1);
assert.equal(normalizePage('0'), 1);
assert.equal(normalizePage('-4'), 1);
assert.equal(normalizePage('3'), 3);
assert.equal(normalizeRegion('china'), 'CHINA');
assert.equal(normalizeRegion('unknown'), 'ALL');

const rows = Array.from({ length: 173 }, (_, index) => ({ id: index + 1 }));
const first = paginate(rows, 1);
assert.equal(first.totalPages, 9);
assert.equal(first.items.length, 20);
assert.equal(first.startNumber, 1);
assert.equal(first.endNumber, 20);
assert.equal(first.hasPrevious, false);
assert.equal(first.hasNext, true);

const last = paginate(rows, 9);
assert.equal(last.items.length, 13);
assert.equal(last.startNumber, 161);
assert.equal(last.endNumber, 173);
assert.equal(last.hasPrevious, true);
assert.equal(last.hasNext, false);

// New articles may increase the number of pages without changing the UI code.
const afterUpdate = paginate([...rows, ...Array.from({ length: 28 }, (_, index) => ({ id: 174 + index }))], 10);
assert.equal(afterUpdate.totalPages, 11);
assert.equal(afterUpdate.page, 10);
assert.equal(afterUpdate.items.length, 20);

// If an update removes the requested final page, clamp to the last page that still exists.
const afterRemoval = paginate(rows.slice(0, 119), 99);
assert.equal(afterRemoval.totalPages, 6);
assert.equal(afterRemoval.page, 6);
assert.equal(afterRemoval.items.length, 19);

const empty = paginate([], 8);
assert.equal(empty.totalPages, 1);
assert.equal(empty.page, 1);
assert.deepEqual(empty.items, []);
assert.equal(empty.startNumber, 0);
assert.equal(empty.endNumber, 0);

console.log('pagination tests passed');
