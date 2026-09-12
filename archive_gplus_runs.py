"""Archive complete local run evidence and verify every member before publishing."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
ARCHIVES = ROOT / 'archives'
EXPERIMENTS = ('time_push_20260912', 'gplus_next_20260912')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ARCHIVES.mkdir(exist_ok=True)
    summary = []
    for experiment in EXPERIMENTS:
        source = ROOT / experiment / 'runs'
        archive = ARCHIVES / (experiment + '_runs.tar.gz')
        if archive.exists():
            raise FileExistsError('Refusing to replace an existing evidence archive: ' + str(archive))
        files = sorted(path for path in source.rglob('*') if path.is_file())
        expected = {path.relative_to(ROOT).as_posix(): sha256(path) for path in files}
        pending = archive.with_suffix(archive.suffix + '.part')
        with pending.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=6, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as bundle:
                    for path in files:
                        name = path.relative_to(ROOT).as_posix()
                        info = bundle.gettarinfo(str(path), arcname=name)
                        info.uid = info.gid = 0
                        info.uname = info.gname = ''
                        info.mtime = 0
                        with path.open('rb') as stream:
                            bundle.addfile(info, stream)
        seen = set()
        with tarfile.open(pending, 'r|gz') as bundle:
            for member in bundle:
                assert member.isfile() and member.name in expected and member.name not in seen
                with bundle.extractfile(member) as stream:
                    assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected[member.name]
                seen.add(member.name)
        assert seen == set(expected)
        assert pending.stat().st_size < 99 * 1024 * 1024, 'Archive exceeds repository file size budget'
        pending.rename(archive)
        tree = hashlib.sha256()
        for name, digest in expected.items():
            tree.update((name + '\0' + digest + '\n').encode('utf-8'))
        record = dict(archive=archive.relative_to(ROOT).as_posix(), source_directory=source.relative_to(ROOT).as_posix(),
                      files=len(files), run_directories=sum(p.is_dir() for p in source.iterdir()),
                      original_bytes=sum(p.stat().st_size for p in files), archive_bytes=archive.stat().st_size,
                      sha256=sha256(archive), content_tree_sha256=tree.hexdigest(),
                      every_member_verified_against_original=True, original_files_preserved=True)
        archive.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        summary.append(record)
        print(json.dumps(record), flush=True)
    (ARCHIVES / 'MANIFEST.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
