import os
from shutil import copyfile
import threading
import queue


class FlattenFolder:
    """
    Flatten a directory
    """

    def __init__(self, dirpath, target, maybeAsync=True):
        self.path = dirpath
        self.target = target

        if maybeAsync:
            self.done = False
            self.lock = threading.Lock()
            self.threads = []
            self.threads_done = []
            self.filesDone = queue.Queue()

    def create_target(self):
        """
        Create target directory
        """
        if not os.path.exists(self.target):
            os.makedirs(self.target)

    def flat(self):
        """
        Flatten a directory
        """

        self.create_target()

        _status = []

        for root, _dirs, files in os.walk(self.path):
            for file in files:
                new_file = os.path.join(self.target, file)
                old_file = os.path.join(root, file)

                if not os.path.exists(new_file):
                    copyfile(old_file, new_file)
                    _status.append((old_file, new_file, True))
                else:
                    _status.append((old_file, new_file, False))

        return _status

    def flatAsync(self):
        """
        Flatten a directory asynchronously
        """

        self.create_target()
        # get max number of threads
        max_threads = len(os.sched_getaffinity(0))

        # create a queue to store the results
        self.filesDone = queue.Queue()

        # create a thread for each chunk
        self.threads = []
        self.threads_done = []

        self.lock = threading.Lock()

        # split the work into chunks according to max_threads
        chunks = self.split_chunks(self.path, max_threads)

        # create a thread for each chunk
        for chunk in chunks:
            if len(chunk) > 0:
                t = threading.Thread(target=self.flat_chunk, args=[chunk])
                self.threads.append(t)
                t.start()

    def is_running(self):
        """
        Check if the flatten is running
        """

        # if async flatten is running
        if self.threads:
            # check if all threads are done
            return len(self.threads) == len(self.threads_done) or self.filesDone.qsize() > 0

        return False

    def join(self):
        """
        Join threads
        """
        for thread in self.threads:
            thread.join()

        self.done = True

    def is_locked(self):
        """
        Check if the lock is locked
        """
        return self.lock.locked()

    @staticmethod
    def split_chunks(path, max_threads):
        """
        Split a directory into chunks
        """

        chunks = []
        for root, _dirs, files in os.walk(path):
            for _file in files:
                chunks.append(root)
                break

        # if there are more chunks than max_threads, create chunks in chunks
        if len(chunks) > max_threads:
            chunks = [chunks[i:i + max_threads]
                     for i in range(0, len(chunks), max_threads)]

        return chunks

    def flat_chunk(self, chunk):
        """
        Flatten a chunk
        """

        # get current thread id
        thread_id = threading.get_ident()

        # if chunk is a list
        if isinstance(chunk, list):
            for _path in chunk:
                self.walk_copy(_path)
        else:
            self.walk_copy(chunk)

        self.lock.acquire()
        self.threads_done.append(thread_id)
        self.lock.release()

    def walk_copy(self, path):
        for root, _dirs, files in os.walk(path):
            for file in files:
                new_file = os.path.join(self.target, file)
                old_file = os.path.join(root, file)

                canCopy = not os.path.exists(new_file)

                # enqueue the result
                self.filesDone.put((old_file, new_file, canCopy))

                if canCopy:
                    copyfile(old_file, new_file)


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        print("Usage: python3 flatten.py <source> <target>")
        sys.exit(1)

    flatten = FlattenFolder(sys.argv[1], sys.argv[2])
    flatten.flatAsync()
    flatten.join()

    while flatten.filesDone.qsize():
        fileDone = flatten.filesDone.get()

        if fileDone is not None:
            (oldFile, newFile, status) = fileDone
            IF_OK_ELSE_FAIL = "OK" if status else "FAIL"

            print("{} -> {}: {}".format(oldFile, newFile, IF_OK_ELSE_FAIL))
