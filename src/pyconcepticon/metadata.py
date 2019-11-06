import urllib.parse

import attr


@attr.s
class Publisher:
    name = attr.ib(
        metadata=dict(ldkey="http://xmlns.com/foaf/0.1/name"),
        default='Max Planck Institute for the Science of Human History')
    place = attr.ib(
        metadata=dict(ldkey="dc:Location"),
        default='Jena')
    url = attr.ib(
        metadata=dict(ldkey="http://xmlns.com/foaf/0.1/homepage"),
        default='https://www.shh.mpg.de')
    contact = attr.ib(
        metadata=dict(ldkey="http://xmlns.com/foaf/0.1/mbox"),
        default='concepticon@shh.mpg.de')


@attr.s
class License:
    name = attr.ib(
        default="Creative Commons Attribution 4.0 International License")
    url = attr.ib(
        default="https://creativecommons.org/licenses/by/4.0/")
    icon = attr.ib(
        default="cc-by.png")


@attr.s
class Metadata:
    publisher = attr.ib(default=Publisher(), validator=attr.validators.instance_of(Publisher))
    license = attr.ib(default=License(), validator=attr.validators.instance_of(License))
    url = attr.ib(default='https://concepticon.clld.org')
    title = attr.ib(default="Concepticon")
    description = attr.ib(default="A Resource for the Linking of Concept Lists")

    @classmethod
    def from_jsonld(cls, d):
        kw = {}
        for k, v in [
            ('dcat:accessURL', 'url'),
            ('dc:title', 'title'),
            ('dc:description', 'description'),
        ]:
            if d.get(k):
                kw[v] = d[k]
        for ldkey, cls_ in [('dc:publisher', Publisher), ('dc:license', License)]:
            ckw = {
                f.name: d.get(ldkey, {}).get(f.metadata.get('ldkey', f.name))
                for f in attr.fields(cls_)}
            kw[cls_.__name__.lower()] = cls_(**{k: v for k, v in ckw.items() if v})
        return cls(**kw)

    @property
    def domain(self):
        return urllib.parse.urlparse(self.url).netloc
