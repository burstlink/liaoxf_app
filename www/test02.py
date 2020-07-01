def parse_qs(qs, a=False, b=1):
    print(qs)
    print(a)
    print(b)

parse_qs("s", True)
module_name = "handler1.handler2"
n = module_name.rfind('.')
name = module_name[n+1:]
print(name)

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace(
        '<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)
print(text2html("liyy"))