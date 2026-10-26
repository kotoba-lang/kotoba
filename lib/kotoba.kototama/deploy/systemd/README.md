# systemd packaging for the kototama component-authority receiver

Fleet recovery packaging moved to
[`kotoba-lang/fleet`](https://github.com/kotoba-lang/fleet) with the T6
placement implementation. This directory now owns only tender-side authority
receiver packaging.

## Component authority receiver

Install `deploy/bin/kototama-authority-daemon`,
`deploy/systemd/kototama-authority-daemon.service`, and an edited copy of
`component-authority.edn.example`. Store the PKCS#12 password only in
`/etc/kototama/component-authority.secret` with mode `0600`.

Key rotation is overlap-first: add the next trusted key, deploy and restart all
receivers, switch Murakumo signing to the next key, then remove the old key.
The envelope audience must equal the node-specific `:audience`.
