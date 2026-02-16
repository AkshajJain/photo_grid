project(
  'photo-grid',
  version: '1.0.0',
  meson_version: '>= 0.59.0',
  default_options: ['prefix=/usr'],
)

python = find_program('python3')

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

subdir('data')
subdir('src')
