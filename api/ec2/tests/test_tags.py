from ...ec2 import tags


class TestTagConvertFunction(object):
    def test_tags_to_list_empty(self):
        assert [] == tags.tags_dict_to_list({})

    def test_tags_to_list_one(self):
        assert [dict(Key='key', Value='value')] == tags.tags_dict_to_list(dict(key='value'))

    def test_tags_to_list_more(self):
        converted = tags.tags_dict_to_list(dict(key='value', key2='value2'))
        expected = [dict(Key='key', Value='value'), dict(Key='key2', Value='value2')]
        assert converted == expected or converted == [expected[1], expected[0]]

    def test_list_to_tags_empty(self):
        assert {} == tags.tags_list_to_dict([])

    def test_list_to_tags_one(self):
        assert dict(key='value') == tags.tags_list_to_dict([dict(Key='key', Value='value')])

    def test_list_to_tags_more(self):
        converted = tags.tags_list_to_dict([dict(Key='key', Value='value'), dict(Key='key2', Value='value2')])
        expected = dict(key='value', key2='value2')
        assert converted == expected
