# CHANGELOG

<!-- version list -->

## v0.15.2 (2026-05-29)

### Bug Fixes

- **docs**: Mention about config/odoo.conf file
  ([`9c85e4b`](https://github.com/trobz/deploy.py/commit/9c85e4b9623b04e5325a853831f76f34b2834d91))

- **update**: Specify config file when updating odoo modules
  ([`5c8c6e3`](https://github.com/trobz/deploy.py/commit/5c8c6e3f8d9c660d7eec7a7e20fd7faa51601b54))


## v0.15.1 (2026-05-28)

### Bug Fixes

- **all commands**: Migrate CLI from click to typer
  ([`07d5181`](https://github.com/trobz/deploy.py/commit/07d5181146bd70a1466f025ba79b31efbfa78cf3))


## v0.15.0 (2026-05-28)

### Features

- **configure, update**: Recursively clone and pull submodules during deployment
  ([`8eece67`](https://github.com/trobz/deploy.py/commit/8eece6739de738651ab8f984b84733dd2ee76e16))


## v0.14.0 (2026-05-25)

### Features

- **configure**: Inject EnvironmentFile from config/server.env when present
  ([`a59dfde`](https://github.com/trobz/deploy.py/commit/a59dfde0c592a2777650d74c61dfb628298e4875))


## v0.13.0 (2026-05-25)

### Features

- **configure,update,status**: Support service type without repo or build
  ([`a9a0abf`](https://github.com/trobz/deploy.py/commit/a9a0abff1624eb60583312e45ad30b719f207872))


## v0.12.0 (2026-05-22)

### Documentation

- **update**: Support multiple databases
  ([`4e9ecd5`](https://github.com/trobz/deploy.py/commit/4e9ecd5daee6acd9effa38dd2570cc4e62ab389c))

### Features

- **update**: Support multi-db
  ([`508441d`](https://github.com/trobz/deploy.py/commit/508441d20f2a6c0e799a2bd274573052c1cee8d6))


## v0.11.1 (2026-05-21)

### Bug Fixes

- **configure**: Skip venv creation when --force and venv already exists
  ([`c7c6209`](https://github.com/trobz/deploy.py/commit/c7c62098443e1b74da50050b9c37bdbdb1d94f64))


## v0.11.0 (2026-05-19)

### Documentation

- **status**: Document --watch flag
  ([`2622671`](https://github.com/trobz/deploy.py/commit/262267193a51e9ad3c07bd5ce08a48e75fd7ca4d))

### Features

- **status**: Add --watch flag to stream logs after status
  ([`0766cc2`](https://github.com/trobz/deploy.py/commit/0766cc2bfa9325a8fd7f925b8195673732f02982))


## v0.10.2 (2026-05-15)

### Bug Fixes

- **site-docs**: Demo with a project
  ([`6f8b9fb`](https://github.com/trobz/deploy.py/commit/6f8b9fbbc5f8ceb8371ac0eb53be560a09ff7e3f))


## v0.10.1 (2026-05-08)

### Bug Fixes

- **site-docs**: Remove markdown page, add --watch option
  ([`e77f9cc`](https://github.com/trobz/deploy.py/commit/e77f9ccad543c3c2fb9553539abea2d4f83c6f23))


## v0.10.0 (2026-05-08)

### Features

- **docs**: Add documentation site with Trobz theme
  ([`934805e`](https://github.com/trobz/deploy.py/commit/934805e7fda1b4bed987511ea06719a481c7e1ec))


## v0.9.0 (2026-05-08)

### Features

- Publish trobz-deploy to pypi
  ([`0fca46c`](https://github.com/trobz/deploy.py/commit/0fca46c542271b8a76e9b4fcac68ed5d506bb1f6))

- Rename folder to prepare for publishing to pypi
  ([`2541f57`](https://github.com/trobz/deploy.py/commit/2541f57012a8e72302630135db8148fad9ecbd34))


## v0.8.0 (2026-05-05)

### Features

- Add --watch flag to deploy update
  ([`ece738f`](https://github.com/trobz/deploy.py/commit/ece738f465e97c4cff39b52512ddfd77f2f654db))


## v0.7.0 (2026-05-05)

### Features

- Add repo_branch parameter support
  ([`94ea20b`](https://github.com/trobz/deploy.py/commit/94ea20ba1ba607b86440e9eedb610261408c218c))


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
