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

## Create the split files for MMDialogue (J-CRe3) dataset

```shell
$ ls data/mmdialogue/Sentences | tr -d '.txt' G -E '^(56130322|56132034|56133195|56130205|56132112|57113854|57113951|57116595|56130258)' | sort > data/mmdialogue/test.txt
$ ls data/mmdialogue/Sentences | tr -d '.txt' G -E '^(56130295|56130204|56131998|56132024|57113485|57113968)' | sort > data/mmdialogue/val.txt
$ difference <(ls data/mmdialogue/Sentences | tr -d '.txt') <(cat data/mmdialogue/val.txt) > train.tmp.txt
$ difference <(cat train.tmp.txt) <(cat data/mmdialogue/test.txt) > train.tmp2.txt
$ sort train.tmp2.txt > data/mmdialogue/train.txt
$ rm train.tmp.txt train.tmp2.txt
$ wc -l data/mmdialogue/test.txt
1360
$ wc -l data/mmdialogue/val.txt
671
$ wc -l data/mmdialogue/train.txt
7853
```

## Preprocess MMDialogue (J-CRe3) dataset

```shell
cd /path/to/multimodal-annotation
mdetr_data_dir=/path/to/mdetr/data
python src/convert_annotation_to_flickr.py -d data/dataset -k data/knp -a data/image_text_annotation --flickr-image-dir ${mdetr_data_dir}/mmdialogue-images --flickr-annotations-dir ${mdetr_data_dir}/mmdialogue/Annotations --flickr-sentences-dir ${mdetr_data_dir}/mmdialogue/Sentences --scenario-ids $(cat dialogue_table.csv | grep full | cut -d, -f1)
```

## Move image files according to the split

```shell
$ cat data/mmdialogue/test.txt | xargs -I{} mv data/mmdialogue-images/{}.png data/mmdialogue-images/test/
$ cat data/mmdialogue/val.txt | xargs -I{} mv data/mmdialogue-images/{}.png data/mmdialogue-images/val/
$ cat data/mmdialogue/train.txt | xargs -I{} mv data/mmdialogue-images/{}.png data/mmdialogue-images/train/
$ ls data/mmdialogue-images/test | wc -l
1360
$ ls data/mmdialogue-images/val | wc -l
671
$ ls data/mmdialogue-images/train | wc -l
7853
```

## Convert MMDialogue to annotation files for MDETR

```shell
$ mkdir -p data/mdetr_annotations_mmdialogue
$ python scripts/pre-training/flickr_combined.py --flickr_path data/mmdialogue --out_path data/mdetr_annotations_mmdialogue
$ ls data/mdetr_annotations_mmdialogue
final_flickr_separateGT_test.json  final_flickr_separateGT_train.json  final_flickr_separateGT_val.json
```
