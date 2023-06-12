# How to prepare datasets

## Download Flickr30k images

Go to [the download page](http://shannon.cs.illinois.edu/DenotationGraph/) and get `flickr30k-images.tar.gz`.

```shell
mv flickr30k-images.tar.gz data
tar zxvf data/flickr30k-images.tar.gz -C data

```

## Download Flickr30k Entities Ja dataset

```shell
$ wget https://github.com/nlab-mpg/Flickr30kEnt-JP/raw/master/Sentences_jp_v2.tgz -P data/Flickr30kEnt-JP
$ tar zxvf data/Flickr30kEnt-JP/Sentences_jp_v2.tgz -C data/Flickr30kEnt-JP
$ ls data/Flickr30kEnt-JP/Sentences_jp_v2
1000092795.txt
...
998845445.txt
$ ls data/Flickr30kEnt-JP/Sentences_jp_v2 | wc -l
31783
```

## Replace Sentences

```shell
cd data/flickr30k_entities
mv Sentences Sentences_en
ln -s ../Flickr30kEnt-JP/Sentences_jp_v2 ./Sentences
```

## Convert Flickr30k Entities Ja dataset to annotation files for MDETR

```shell
$ mkdir -p data/mdetr_annotations_ja
$ python scripts/pre-training/flickr_combined.py --flickr_path data/flickr30k_entities --out_path data/mdetr_annotations_ja
$ ls data/mdetr_annotations_ja
final_flickr_separateGT_test.json  final_flickr_separateGT_train.json  final_flickr_separateGT_val.json
```

## Convert MMDialogue to annotation files for MDETR

```shell
$ mkdir -p data/mdetr_annotations_mmdialogue
$ python scripts/pre-training/flickr_combined.py --flickr_path data/mmdialogue --out_path data/mdetr_annotations_mmdialogue
$ ls data/mdetr_annotations_mmdialogue
final_flickr_separateGT_test.json  final_flickr_separateGT_train.json  final_flickr_separateGT_val.json
```
