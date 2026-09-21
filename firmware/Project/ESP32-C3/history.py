class RingHistory:
    def __init__(self, capacity):
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._items = [None] * capacity
        self._start = 0
        self._size = 0

    def append(self, item):
        index = (self._start + self._size) % self.capacity
        if self._size == self.capacity:
            index = self._start
            self._start = (self._start + 1) % self.capacity
        else:
            self._size += 1
        self._items[index] = item

    def latest(self):
        if not self._size:
            return None
        return self._items[(self._start + self._size - 1) % self.capacity]

    def to_list(self):
        return [self._items[(self._start + i) % self.capacity]
                for i in range(self._size)]

    def __len__(self):
        return self._size

