#!/usr/bin/env python3
import json, os, pathlib, shlex, subprocess, sys, tempfile
new = sys.argv[1]
old = '/usr/sbin/modprobe'

def run(argv, env=None):
    p = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return {'status': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}

def exact(args):
    return 'KMOD1;' + ''.join(f'{len(a)}:{a},' for a in args)

def cli_case(root, label, builder, expected):
    d = root / label; d.mkdir(); conf = d / 'config dir'; conf.mkdir(); receipt = d / 'receipt'; receipt.mkdir()
    helper = d / 'helper.sh'
    helper.write_text(
        '#!/bin/sh\nset -eu\n'
        f'printf "%s\\n" "${{KMOD_MODPROBE_OPTIONS_EXACT-}}" > {shlex.quote(str(receipt / "exact"))}\n'
        f'printf "%s\\n" "${{KMOD_MODPROBE_OPTIONS_BASE_LEN-}}" > {shlex.quote(str(receipt / "base"))}\n'
    )
    helper.chmod(0o755)
    (conf / 'case.conf').write_text(f'install outer-{label} {helper}\n')
    argv = builder(conf, f'outer-{label}')
    result = run(argv)
    observed = (receipt / 'exact').read_text().strip() if (receipt / 'exact').exists() else ''
    return {
        'status': result['status'], 'stderr': result['stderr'],
        'base_len': (receipt / 'base').read_text().strip() if (receipt / 'base').exists() else '',
        'observed': observed, 'expected': exact(expected(conf)),
    }

def base_stability(root):
    conf = root / 'stable config'; conf.mkdir(); lengths = root / 'stable-lengths'; output = root / 'stable-output'
    config = [
        'blacklist stable_marker',
        "install stable-one /bin/sh -c 'printf \"%s %s %s\\\\n\" \"${KMOD_MODPROBE_OPTIONS_BASE_LEN-}\" \"${#KMOD_MODPROBE_OPTIONS_EXACT}\" \"${#MODPROBE_OPTIONS}\" >> " + shlex.quote(str(lengths)) + "; exec " + shlex.quote(new) + " stable-two'",
        "install stable-two /bin/sh -c 'printf \"%s %s %s\\\\n\" \"${KMOD_MODPROBE_OPTIONS_BASE_LEN-}\" \"${#KMOD_MODPROBE_OPTIONS_EXACT}\" \"${#MODPROBE_OPTIONS}\" >> " + shlex.quote(str(lengths)) + "; exec " + shlex.quote(new) + " stable-three'",
        "install stable-three /bin/sh -c 'printf \"%s %s %s\\\\n\" \"${KMOD_MODPROBE_OPTIONS_BASE_LEN-}\" \"${#KMOD_MODPROBE_OPTIONS_EXACT}\" \"${#MODPROBE_OPTIONS}\" >> " + shlex.quote(str(lengths)) + "; exec " + shlex.quote(new) + " -c > " + shlex.quote(str(output)) + "'",
    ]
    (conf / 'stable.conf').write_text('\n'.join(config) + '\n')
    env = os.environ.copy(); env['MODPROBE_OPTIONS'] = '-q'
    result = run([new, '-C', str(conf), 'stable-one'], env)
    rows = lengths.read_text().splitlines() if lengths.exists() else []
    marker = output.read_text().splitlines().count('blacklist stable_marker') if output.exists() else 0
    return {'run': result, 'lengths': rows, 'marker': marker}

def mixed_versions(root):
    representable = root / 'representable config'; representable.mkdir(); old_out = root / 'new-old.txt'
    (representable / 'a.conf').write_text(
        'blacklist mixed-marker\n'
        f'install new-to-old {old} -c > {old_out}\n'
    )
    new_old = run([new, '-C', str(representable), 'new-to-old'])
    new_old_marker = old_out.read_text().splitlines().count('blacklist mixed_marker') if old_out.exists() else 0

    old_parent = root / 'old parent config'; old_parent.mkdir(); old_new_out = root / 'old-new.txt'
    (old_parent / 'a.conf').write_text(
        'blacklist old-new-marker\n'
        f'install old-to-new {new} -c > {old_new_out}\n'
    )
    old_new = run([old, '-C', str(old_parent), 'old-to-new'])
    old_new_marker = old_new_out.read_text().splitlines().count('blacklist old_new_marker') if old_new_out.exists() else 0

    bad = root / "bad'\" config"; bad.mkdir(); bad_out = root / 'bad-old.txt'
    (bad / 'a.conf').write_text(
        'blacklist bad-marker\n'
        f'install new-to-old-bad {old} -c > {bad_out}\n'
    )
    bad_run = run([new, '-C', str(bad), 'new-to-old-bad'])
    return {
        'new_old': {'run': new_old, 'marker': new_old_marker},
        'old_new': {'run': old_new, 'marker': old_new_marker},
        'new_old_unrepresentable': {'run': bad_run, 'output': bad_out.read_text() if bad_out.exists() else ''},
    }

with tempfile.TemporaryDirectory(prefix='kmod-provenance-') as td:
    root = pathlib.Path(td)
    cli = {
        'short_attached': cli_case(root, 'short-attached', lambda c, m: [new, '-C' + str(c), m], lambda c: ['-C', str(c)]),
        'long_attached': cli_case(root, 'long-attached', lambda c, m: [new, '--config=' + str(c), m], lambda c: ['-C', str(c)]),
        'after_nonoption': cli_case(root, 'after-nonoption', lambda c, m: [new, m, '-C', str(c)], lambda c: ['-C', str(c)]),
        'cluster': cli_case(root, 'cluster', lambda c, m: [new, '-qv', '-C', str(c), m], lambda c: ['-q', '-v', '-C', str(c)]),
    }
    repeated = root / 'repeated'; repeated.mkdir(); c1 = repeated / 'one'; c2 = repeated / 'two'; c1.mkdir(); c2.mkdir(); receipt = repeated / 'receipt'; receipt.mkdir(); helper = repeated / 'helper.sh'
    helper.write_text('#!/bin/sh\nset -eu\nprintf "%s\\n" "${KMOD_MODPROBE_OPTIONS_EXACT-}" > ' + shlex.quote(str(receipt / 'exact')) + '\nprintf "%s\\n" "${KMOD_MODPROBE_OPTIONS_BASE_LEN-}" > ' + shlex.quote(str(receipt / 'base')) + '\n'); helper.chmod(0o755)
    (c1 / 'a.conf').write_text(f'install outer-repeated {helper}\n')
    rr = run([new, '-C', str(c1), '--config=' + str(c2), 'outer-repeated'])
    cli['repeated'] = {'status': rr['status'], 'stderr': rr['stderr'], 'stdout': rr['stdout'], 'base_len': (receipt / 'base').read_text().strip() if (receipt / 'base').exists() else '', 'observed': (receipt / 'exact').read_text().strip() if (receipt / 'exact').exists() else '', 'expected': exact(['-C', str(c1), '-C', str(c2)])}

    stable = base_stability(root)
    mixed = mixed_versions(root)
    result = {'modprobe': new, 'cli': cli, 'base_stability': stable, 'mixed_versions': mixed}
    print(json.dumps(result, indent=2, sort_keys=True))

    for name, case in cli.items():
        assert case['status'] == 0, (name, case)
        assert case['base_len'] == '0', (name, case)
        assert case['observed'] == case['expected'], (name, case)
    assert stable['run']['status'] == 0 and stable['marker'] == 1
    assert len(stable['lengths']) == 3 and len(set(stable['lengths'])) == 1
    assert all(row.startswith('2 ') for row in stable['lengths'])
    assert mixed['new_old']['run']['status'] == 0 and mixed['new_old']['marker'] == 1
    assert mixed['old_new']['run']['status'] == 0 and mixed['old_new']['marker'] == 0
    assert mixed['new_old_unrepresentable']['run']['status'] != 0
    assert '--kmod-exact-options-required' in mixed['new_old_unrepresentable']['run']['stderr']
