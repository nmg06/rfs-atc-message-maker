"""Create shareable archives from explicit allowlists, excluding private state."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def archive(target, root, files, prefix):
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for file in sorted(files):
            relative=file.relative_to(root)
            if '__pycache__' in relative.parts or file.suffix in ('.pyc','.parquet','.bak'):
                continue
            out.write(file, str(Path(prefix)/relative))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.bundle/'data').exists():
        raise ValueError('Private data directory detected in release bundle; refusing to distribute it')
    source_files=[p for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.md','.txt','.bat','.spec')
                  and p.name not in ('CODEX_TASK.md','RFS_TASK.md','MessageMaker.spec','translation_inventory.txt')]
    source_files += [source/'.gitignore']
    for name in ('.github','assets','docs','finder','fuel','scripts','tests'):
        source_files += [p for p in (source/name).rglob('*') if p.is_file()]
    portable=args.output/'RFS-ATC-Message-Maker-Windows-v5.zip'
    sources=args.output/'RFS-ATC-Message-Maker-Sources-v5.zip'
    archive(portable,args.bundle,[p for p in args.bundle.rglob('*') if p.is_file()],'RFSATCMessageMaker')
    archive(sources,source,source_files,'RFS-ATC-Message-Maker')
    hashes=[]
    for file in (portable,sources,args.bundle/'RFSATCMessageMaker.exe'):
        with file.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        hashes.append(f'{digest}  {file.name}')
        print(f'{file}: {file.stat().st_size:,} bytes')
    (args.output/'SHA256SUMS-v5.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
