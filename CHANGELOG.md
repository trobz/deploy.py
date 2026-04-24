# CHANGELOG

<!-- version list -->

## v0.6.1 (2026-04-24)

### Bug Fixes

- **ci-workflow**: update actions for node 24
  ([`32875ee`](https://github.com/trobz/deploy.py/commit/32875ee24c4eb82241fe0b96a4426b690a1f1eee))

- **ci-workflow**: update actions for node 24
  ([`0979da0`](https://github.com/trobz/deploy.py/commit/0979da01f315e65f5ed65519d479ac552ba20168))

## v0.6.0 (2026-04-16)

### Features

- **configure,update**: Rename requirement to requirements, support list
  ([`2b42e20`](https://github.com/trobz/deploy.py/commit/2b42e20d94e94327a0cf530c1c01bc00bf71605e))

- **configure,update**: Support pip package deployment for python type
  ([`1596195`](https://github.com/trobz/deploy.py/commit/1596195bc5e3d130b0e2743a659399e36b186596))

- **templates**: Load .env file in python systemd unit if present
  ([`7bf3346`](https://github.com/trobz/deploy.py/commit/7bf3346189b588ef6c629a5be0a19f0cfb4db79f))


## v0.5.0 (2026-04-13)

### Bug Fixes

- **configure**: Move git aggregate command under eff_type odoo
  ([`f0ce239`](https://github.com/trobz/deploy.py/commit/f0ce2394ded70b3c55418c20d7f52885402f4ae9))

### Features

- **configure**: Add repo_subdir support for monorepo deployments
  ([`1cadb31`](https://github.com/trobz/deploy.py/commit/1cadb31956e4a1a0748c08b8819ad98aa0f863ce))

- **update**: Add repo_subdir support for monorepo deployments
  ([`5704f30`](https://github.com/trobz/deploy.py/commit/5704f300f859c8a353f3ddb2e30bd03b4cd5695b))


## v0.4.4 (2026-04-10)

### Bug Fixes

- **template**: Wrap start command in bash -c ""
  ([`3562052`](https://github.com/trobz/deploy.py/commit/3562052171c4a7450bdb5fdac8c79014b7247a84))


## v0.4.3 (2026-04-10)

### Bug Fixes

- **action.yml**: Change secrets and vars to inputs
  ([`1f8c330`](https://github.com/trobz/deploy.py/commit/1f8c330d221a5e094797507b6ca08a34a4ac57b2))


## v0.4.2 (2026-04-08)

### Bug Fixes

- **action.yml**: Intercept type, build_cmd, and exec_start settings
  ([`66f99d2`](https://github.com/trobz/deploy.py/commit/66f99d2fd35c5c531d600e2622baf18ffe1b4983))


## v0.4.1 (2026-04-08)

### Bug Fixes

- **update**: Install and use click-odoo-update in venv
  ([`c36027e`](https://github.com/trobz/deploy.py/commit/c36027e8bca08dfb35fd5d14d6b90f56b9548650))


## v0.4.0 (2026-04-07)

### Features

- Add /action.yml to repo
  ([`6eebbc9`](https://github.com/trobz/deploy.py/commit/6eebbc9eded9f2594a58776248d35b9599a15a3c))


## v0.3.3 (2026-04-02)

### Bug Fixes

- Activate venv for click-odoo-update
  ([`fb1b775`](https://github.com/trobz/deploy.py/commit/fb1b7751a01a033d4d8cba70d0c0f4e67b3d6c62))


## v0.3.2 (2026-04-02)

### Bug Fixes

- **update**: Always confirm when update venv
  ([`1c25356`](https://github.com/trobz/deploy.py/commit/1c253565a620edaae1c42dcc2711a03bf0adb91c))


## v0.3.1 (2026-04-01)

### Bug Fixes

- Remove extra space before ellipsis in log messages
  ([`650d3f7`](https://github.com/trobz/deploy.py/commit/650d3f7cf04854bec3bd3eccd859abb103cac91b))


## v0.3.0 (2026-03-31)

### Bug Fixes

- Update: correct click-odoo-update statement
  ([`aefee8e`](https://github.com/trobz/deploy.py/commit/aefee8e7fda8415cfc9eaeef8ce1061f0bbc386c))

### Features

- Improve configure and update commands
  ([`5283f9c`](https://github.com/trobz/deploy.py/commit/5283f9c299978ad8d7e48c457730fe54072f197e))


## v0.2.0 (2026-03-26)

### Features

- Improve configure command
  ([`c818f69`](https://github.com/trobz/deploy.py/commit/c818f6909f8193e4e9a112457561784e1beb7de6))


## v0.1.1 (2026-03-25)

### Bug Fixes

- Add --clear to uv venv when --force is used
  ([`5786ff3`](https://github.com/trobz/deploy.py/commit/5786ff3a5977921b09ddf04cbe66640a87214780))


## v0.1.0 (2026-03-16)

- Initial Release
