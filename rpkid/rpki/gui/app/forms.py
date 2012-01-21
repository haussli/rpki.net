# $Id$
"""
Copyright (C) 2010, 2011  SPARTA, Inc. dba Cobham Analytic Solutions
Copyright (C) 2012  SPARTA, Inc. a Parsons Company

Permission to use, copy, modify, and distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND SPARTA DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS.  IN NO EVENT SHALL SPARTA BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

from django import forms

from rpki import resource_set
from rpki.gui.app import models
from rpki.exceptions import BadIPResource


class AddConfForm(forms.Form):
    handle = forms.CharField(required=True,
            help_text='your handle for your rpki instance')
    run_rpkid = forms.BooleanField(required=False, initial=True,
            label='Run rpkid?',
            help_text='do you want to run your own instance of rpkid?')
    rpkid_server_host = forms.CharField(initial='rpkid.example.org',
            label='rpkid hostname',
            help_text='publicly visible hostname for your rpkid instance')
    rpkid_server_port = forms.IntegerField(initial=4404,
            label='rpkid port')
    run_pubd = forms.BooleanField(required=False, initial=False,
            label='Run pubd?',
            help_text='do you want to run your own instance of pubd?')
    pubd_server_host = forms.CharField(initial='pubd.example.org',
            label='pubd hostname',
            help_text='publicly visible hostname for your pubd instance')
    pubd_server_port = forms.IntegerField(initial=4402, label='pubd port')
    pubd_contact_info = forms.CharField(initial='repo-man@rpki.example.org',
            label='Pubd contact',
            help_text='email address for the operator of your pubd instance')


class ImportForm(forms.Form):
    '''Form used for uploading parent/child identity xml files'''
    handle = forms.CharField(max_length=30,
            help_text='your name for this entity')
    xml = forms.FileField(help_text='xml filename')


class GhostbusterRequestForm(forms.ModelForm):
    """
    Generate a ModelForm with the subset of parents for the current
    resource handle.
    """
    # override default form field
    parent = forms.ModelChoiceField(queryset=None, required=False,
            help_text='Specify specific parent, or none for all parents')

    # override full_name.  it is required in the db schema, but we allow the
    # user to skip it and default from family+given name
    full_name = forms.CharField(max_length=40, required=False,
            help_text='automatically generated from family and given names if left blank')

    def __init__(self, issuer, *args, **kwargs):
        super(GhostbusterRequestForm, self).__init__(*args, **kwargs)
        self.fields['parent'].queryset = models.Parent.objects.filter(issuer=issuer)

    class Meta:
        model = models.GhostbusterRequest
        exclude = ('issuer', 'vcard')

    def clean(self):
        family_name = self.cleaned_data.get('family_name')
        given_name = self.cleaned_data.get('given_name')
        if not all([family_name, given_name]):
            raise forms.ValidationError, 'Family and Given names must be specified'

        email = self.cleaned_data.get('email_address')
        postal = self.cleaned_data.get('postal_address')
        telephone = self.cleaned_data.get('telephone')
        if not any([email, postal, telephone]):
            raise forms.ValidationError, 'One of telephone, email or postal address must be specified'

        # if the full name is not specified, default to given+family
        fn = self.cleaned_data.get('full_name')
        if not fn:
            self.cleaned_data['full_name'] = '%s %s' % (given_name, family_name)

        return self.cleaned_data


def ImportChildForm(parent_conf, *args, **kwargs):
    class wrapped(forms.Form):
        handle = forms.CharField(max_length=30, help_text="Child's RPKI handle")
        xml = forms.FileField(help_text="Child's identity.xml file")

        def clean_handle(self):
            if parent_conf.children.filter(handle=self.cleaned_data['handle']):
                raise forms.ValidationError, "a child with that handle already exists"
            return self.cleaned_data['handle']

    return wrapped(*args, **kwargs)


def ImportParentForm(conf, *args, **kwargs):
    class wrapped(forms.Form):
        handle = forms.CharField(max_length=30, help_text="Parent's RPKI handle", required=True)
        xml = forms.FileField(help_text="XML response from parent", required=True,
                widget=forms.FileInput(attrs={'class': 'xlarge'}))

        def clean_handle(self):
            if conf.parents.filter(handle=self.cleaned_data['handle']):
                raise forms.ValidationError, "a parent with that handle already exists"
            return self.cleaned_data['handle']

    return wrapped(*args, **kwargs)


class ImportRepositoryForm(forms.Form):
    parent_handle = forms.CharField(max_length=30, required=False, help_text='(optional)')
    xml = forms.FileField(help_text='xml file from repository operator')


class ImportPubClientForm(forms.Form):
    xml = forms.FileField(help_text='xml file from publication client')


def ChildWizardForm(parent, *args, **kwargs):
    class wrapped(forms.Form):
        handle = forms.CharField(max_length=30, help_text='handle for new child')
        #create_user = forms.BooleanField(help_text='create a new user account for this handle?')
        #password = forms.CharField(widget=forms.PasswordInput, help_text='password for new user', required=False)
        #password2 = forms.CharField(widget=forms.PasswordInput, help_text='repeat password', required=False)

        def clean_handle(self):
            if parent.children.filter(handle=self.cleaned_data['handle']):
                raise forms.ValidationError, 'a child with that handle already exists'
            return self.cleaned_data['handle']

    return wrapped(*args, **kwargs)


class ROARequest(forms.Form):
    """Form for entering a ROA request.

    Handles both IPv4 and IPv6."""

    asn = forms.IntegerField()
    prefix = forms.CharField(max_length=50)
    max_prefixlen = forms.CharField(required=False)

    def _as_resource_range(self):
        prefix = self.cleaned_data.get('prefix')
        try:
            r = resource_set.resource_range_ipv4.parse_str(prefix)
        except BadIPResource:
            r = resource_set.resource_range_ipv6.parse_str(prefix)
        return r

    def clean_asn(self):
        value = self.cleaned_data.get('asn')
        if value < 0:
            raise forms.ValidationError, 'AS must be a positive value or 0'
        return value

    def clean_prefix(self):
        try:
            r = self._as_resource_range()
        except:
            raise forms.ValidationError, 'invalid IP address'
        return str(r)

    def clean_max_prefixlen(self):
        v = self.cleaned_data.get('max_prefixlen')
        if v:
            if v[0] == '/':
                v = v[1:]  # allow user to specify /24
            if int(v) < 0:
                raise forms.ValidationError, \
                        'max prefix length must be positive or 0'
        return v

    def clean(self):
        if 'prefix' in self.cleaned_data:
            r = self._as_resource_range()
            max_prefixlen = self.cleaned_data.get('max_prefixlen')
            max_prefixlen = int(max_prefixlen) if max_prefixlen else r.prefixlen()
            if max_prefixlen < r.prefixlen():
                raise (forms.ValidationError,
                        'max prefix length must be greater than or equal to the prefix length')
            if max_prefixlen > r.datum_type.bits:
                raise forms.ValidationError, \
                        'max prefix length (%d) is out of range for IP version (%d)' % (max_prefixlen, r.datum_type.bits)
            self.cleaned_data['max_prefixlen'] = str(max_prefixlen)

        return self.cleaned_data

# vim:sw=4 ts=8 expandtab
